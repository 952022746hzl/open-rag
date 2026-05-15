"""多格式文档解析器。

支持 PDF / DOCX / XLSX / PPTX / TXT / MD 六种格式，
将文件字节流解析为带位置元数据的分节文本结构，供后续分块与向量化使用。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from io import BytesIO

import fitz  # PyMuPDF
import openpyxl
from docx import Document as DocxDocument
from pptx import Presentation

SUPPORTED_TYPES: frozenset[str] = frozenset({"pdf", "docx", "xlsx", "pptx", "txt", "md"})


@dataclass
class ParsedSection:
    """文档中的一个逻辑分节。

    Attributes:
        content: 该节的纯文本内容。
        source_location: 来源标识，如页码、Sheet 名或幻灯片编号；
            无结构来源时为 None。
    """

    content: str
    source_location: str | None = None


@dataclass
class ParsedDocument:
    """解析后的文档，由若干逻辑分节组成。

    Attributes:
        sections: 各分节列表，按文档原始顺序排列，已过滤空节。
    """

    sections: list[ParsedSection] = field(default_factory=list)

    def full_text(self) -> str:
        """返回所有分节拼接后的完整纯文本。

        Returns:
            各节内容以双换行符连接的字符串，跳过空白节。
        """
        return "\n\n".join(s.content for s in self.sections if s.content.strip())


def parse_document(data: bytes, file_type: str) -> ParsedDocument:
    """根据文件类型解析文档字节流，返回结构化文本。

    Args:
        data: 文档的原始字节内容。
        file_type: 文件扩展名（含点或不含均可），如 "pdf" 或 ".docx"。

    Returns:
        解析后的 ParsedDocument，各节携带位置元数据。

    Raises:
        ValueError: file_type 不在支持列表中时抛出，调用方应在此之前完成格式校验。
    """
    ft = file_type.lower().lstrip(".")
    if ft not in SUPPORTED_TYPES:
        raise ValueError(f"不支持的文件类型：{ft}，支持范围：{', '.join(sorted(SUPPORTED_TYPES))}")

    _parsers = {
        "pdf": _parse_pdf,
        "docx": _parse_docx,
        "xlsx": _parse_xlsx,
        "pptx": _parse_pptx,
        "txt": _parse_txt,
        "md": _parse_md,
    }
    return _parsers[ft](data)


# ---------------------------------------------------------------------------
# 各格式解析实现
# ---------------------------------------------------------------------------

def _parse_pdf(data: bytes) -> ParsedDocument:
    sections: list[ParsedSection] = []
    with fitz.open(stream=data, filetype="pdf") as doc:
        for page in doc:
            text = page.get_text().strip()
            if text:
                sections.append(ParsedSection(
                    content=text,
                    source_location=f"第{page.number + 1}页",
                ))
    return ParsedDocument(sections=sections)


def _parse_docx(data: bytes) -> ParsedDocument:
    doc = DocxDocument(BytesIO(data))
    lines: list[str] = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if text:
            lines.append(text)
    content = "\n".join(lines)
    return ParsedDocument(sections=[ParsedSection(content=content)])


def _parse_xlsx(data: bytes) -> ParsedDocument:
    wb = openpyxl.load_workbook(BytesIO(data), read_only=True, data_only=True)
    sections: list[ParsedSection] = []
    try:
        for sheet in wb.worksheets:
            rows: list[str] = []
            for row in sheet.iter_rows(values_only=True):
                cells = [str(cell) if cell is not None else "" for cell in row]
                row_text = "\t".join(cells).rstrip()
                if row_text.strip():
                    rows.append(row_text)
            if rows:
                sections.append(ParsedSection(
                    content="\n".join(rows),
                    source_location=sheet.title,
                ))
    finally:
        wb.close()
    return ParsedDocument(sections=sections)


def _parse_pptx(data: bytes) -> ParsedDocument:
    prs = Presentation(BytesIO(data))
    sections: list[ParsedSection] = []
    for i, slide in enumerate(prs.slides, start=1):
        texts: list[str] = []
        for shape in slide.shapes:
            if shape.has_text_frame:
                for para in shape.text_frame.paragraphs:
                    text = para.text.strip()
                    if text:
                        texts.append(text)
        if texts:
            sections.append(ParsedSection(
                content="\n".join(texts),
                source_location=f"第{i}张幻灯片",
            ))
    return ParsedDocument(sections=sections)


def _parse_txt(data: bytes) -> ParsedDocument:
    text = data.decode("utf-8", errors="replace").strip()
    return ParsedDocument(sections=[ParsedSection(content=text)])


def _parse_md(data: bytes) -> ParsedDocument:
    text = data.decode("utf-8", errors="replace")
    text = _strip_markdown(text).strip()
    return ParsedDocument(sections=[ParsedSection(content=text)])


# ---------------------------------------------------------------------------
# Markdown 语法剥离
# ---------------------------------------------------------------------------

# 围栏代码块：保留代码内容，去除围栏和语言标注
_RE_FENCED_CODE = re.compile(r"```[^\n]*\n([\s\S]*?)```", re.MULTILINE)
# 行内代码：保留代码内容，去除反引号
_RE_INLINE_CODE = re.compile(r"`([^`\n]+)`")
# 标题标记
_RE_HEADING = re.compile(r"^#{1,6}\s+", re.MULTILINE)
# 加粗与斜体：***text***、**text**、*text*、___text___、__text__、_text_
_RE_BOLD_ITALIC = re.compile(r"\*{1,3}([^*\n]+)\*{1,3}|_{1,3}([^_\n]+)_{1,3}")
# 图片（须先于链接匹配）：![alt](url) → alt
_RE_IMAGE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
# 链接：[text](url) → text
_RE_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
# 引用块
_RE_BLOCKQUOTE = re.compile(r"^>\s?", re.MULTILINE)
# 分割线
_RE_HR = re.compile(r"^[-*_]{3,}\s*$", re.MULTILINE)
# HTML 标签
_RE_HTML_TAG = re.compile(r"<[^>]+>")
# 连续空行压缩
_RE_BLANK_LINES = re.compile(r"\n{3,}")


def _strip_markdown(text: str) -> str:
    """去除 Markdown 语法标记，保留纯文本内容。

    Args:
        text: 原始 Markdown 字符串。

    Returns:
        去除语法标记后的纯文本，段落间保留最多一个空行。
    """
    text = _RE_FENCED_CODE.sub(lambda m: m.group(1).strip(), text)
    text = _RE_INLINE_CODE.sub(lambda m: m.group(1), text)
    text = _RE_HEADING.sub("", text)
    text = _RE_BOLD_ITALIC.sub(lambda m: m.group(1) if m.group(1) is not None else m.group(2), text)
    text = _RE_IMAGE.sub(lambda m: m.group(1), text)
    text = _RE_LINK.sub(lambda m: m.group(1), text)
    text = _RE_BLOCKQUOTE.sub("", text)
    text = _RE_HR.sub("", text)
    text = _RE_HTML_TAG.sub("", text)
    text = _RE_BLANK_LINES.sub("\n\n", text)
    return text
