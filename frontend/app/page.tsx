'use client';

/**
 * 根路由：根据认证状态跳转。
 *
 * - 加载中：显示全屏 spinner，等待 AuthProvider 恢复会话
 * - 已认证：跳转到 /chat（主功能页）
 * - 未认证：跳转到 /login
 */

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

import { useAuth } from '@/contexts/auth-context';

export default function RootPage() {
  const { isAuthenticated, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading) {
      router.replace(isAuthenticated ? '/chat' : '/login');
    }
  }, [isAuthenticated, isLoading, router]);

  return (
    <main className="flex min-h-screen items-center justify-center">
      <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-600 border-t-transparent" />
    </main>
  );
}
