"""多轮问答业务服务层。

流程：检索相关 chunk → 拼接历史 + 参考资料 Prompt → 调用 DeepSeek →
自动重试（context_length_exceeded）→ 持久化记录 → 返回带引用的响应。
"""

from datetime import datetime, timezone

import openai
from fastapi import HTTPException, status

from app.api.deps import CurrentUser
from app.config import settings
from app.core.llm import chat_complete
from app.models.qa import QaRecord
from app.repositories.document_repo import DocumentRepo
from app.repositories.qa_repo import QaRepo
from app.schemas.chat import ChatRequest, ChatResponse, Citation
from app.schemas.search import SearchRequest, SearchResultItem
from app.services.search_service import SearchService

_SYSTEM_PROMPT = (
    "你是一个AI面试助手助手，只基于提供的参考资料回答问题。"
    "如果参考资料中没有相关信息，明确告知用户。"
    "回答要结构清晰，引用资料中的原文支撑观点。"

    # "你是一个工厂知识库助手，只基于提供的参考资料回答问题。"
    # "如果参考资料中没有相关信息，明确告知用户。"
    # "回答要结构清晰，引用资料中的原文支撑观点。"
)


def _build_messages(
    question: str,
    history: list[QaRecord],
    results: list[SearchResultItem],
) -> list[dict]:
    """组装发送给 LLM 的消息列表。

    格式：system → 历史 user/assistant 对 → 当前问题（附参考资料）。

    Args:
        question: 当前用户问题。
        history: 按时间升序排列的历史记录。
        results: 本轮检索到的相关 chunk 列表。

    Returns:
        OpenAI message 格式的字典列表。
    """
    messages: list[dict] = [{"role": "system", "content": _SYSTEM_PROMPT}]

    for record in history:
        messages.append({"role": "user", "content": record.question})
        messages.append({"role": "assistant", "content": record.answer})

    refs = []
    for r in results:
        loc = f"，来源: {r.source_location}" if r.source_location else ""
        refs.append(f"[文档: {r.document_name}{loc}]\n{r.snippet}")

    context_text = "\n\n".join(refs) if refs else "（无相关参考资料）"
    user_message = f"{question}\n\n参考资料：\n{context_text}"
    messages.append({"role": "user", "content": user_message})

    return messages


class ChatService:
    """多轮问答业务逻辑。

    Attributes:
        search_svc: 语义检索服务，用于获取相关 chunk。
        qa_repo: 问答记录数据访问仓储。
    """

    def __init__(self, doc_repo: DocumentRepo, qa_repo: QaRepo):
        self.search_svc = SearchService(doc_repo)
        self.qa_repo = qa_repo

    async def chat(self, req: ChatRequest, current_user: CurrentUser) -> ChatResponse:
        """执行一轮问答：检索 → 构建 Prompt → LLM 生成 → 持久化 → 返回。

        session_id 为 None 时自动创建新会话；提供时校验归属权。
        若 LLM 返回 context_length_exceeded，自动逐轮缩小历史窗口后重试。

        Args:
            req: 问答请求，含会话 ID、问题、检索参数及过滤条件。
            current_user: 已通过 JWT 认证的当前用户。

        Returns:
            包含 session_id、turn_id、答案及引用列表的响应体。

        Raises:
            HTTPException: 会话不存在或不属于当前用户返回 404；LLM 调用失败返回 500。
        """
        # 获取或创建会话
        if req.session_id is None:
            session = await self.qa_repo.create_session(current_user.user_id)
        else:
            session = await self.qa_repo.get_session(req.session_id)
            if session is None or session.user_id != current_user.user_id:
                raise HTTPException(status.HTTP_404_NOT_FOUND, detail="会话不存在")

        # 混合检索相关 chunk
        search_resp = await self.search_svc.search(
            SearchRequest(
                query=req.question,
                top_k=req.top_k,
                score_threshold=req.score_threshold,
                filter=req.filter,
            ),
            current_user,
        )
        results = search_resp.results

        # 查询历史，滑动窗口重试
        history = await self.qa_repo.get_history(
            session.session_id, limit=settings.CHAT_HISTORY_WINDOW
        )

        window = len(history)
        window_reduced = False
        answer = ""
        tokens_used = 0

        while True:
            messages = _build_messages(req.question, history[-window:] if window else [], results)
            try:
                answer, tokens_used = await chat_complete(messages)
                break
            except openai.BadRequestError as e:
                if window > 1 and "context_length" in str(e).lower():
                    window -= 1
                    window_reduced = True
                else:
                    raise HTTPException(
                        status.HTTP_500_INTERNAL_SERVER_ERROR, detail="LLM 调用失败"
                    ) from e

        # 构建引用列表
        citations = [
            Citation(
                chunk_id=r.chunk_id,
                document_id=r.document_id,
                document_name=r.document_name,
                source_location=r.source_location,
                snippet=r.snippet,
                download_url=r.download_url,
            )
            for r in results
        ]

        # 持久化记录
        turn_id = session.turn_count + 1
        context = {
            "citations": [c.model_dump() for c in citations],
            "tokens_used": tokens_used,
            "model": settings.OPENAI_CHAT_MODEL,
            "window_reduced": window_reduced,
        }
        await self.qa_repo.save_record(
            session_id=session.session_id,
            turn_id=turn_id,
            question=req.question,
            answer=answer,
            context=context,
        )

        return ChatResponse(
            session_id=session.session_id,
            turn_id=turn_id,
            question=req.question,
            answer=answer,
            citations=citations,
            timestamp=datetime.now(timezone.utc),
        )
