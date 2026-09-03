"use client";

import React, { useEffect, useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { Loader2, AlertCircle, CheckCircle2, ArrowLeft } from "lucide-react";
import Link from "next/link";
import { setAuthToken } from "@/lib/api";

function GitHubCallbackContent() {
  const searchParams = useSearchParams();
  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    async function handleCallback() {
      const code = searchParams.get("code");
      const error = searchParams.get("error");
      const errorDescription = searchParams.get("error_description");

      if (error) {
        setStatus("error");
        setErrorMessage(errorDescription || error || "GitHub authorization was denied or canceled.");
        return;
      }

      if (!code) {
        setStatus("error");
        setErrorMessage("No authorization code received from GitHub.");
        return;
      }

      try {
        // Dynamically resolve API URL
        const proto = window.location.protocol;
        const hostname = window.location.hostname;
        const apiUrl = window.location.port === "3000"
          ? `${proto}//${hostname}:8000/api/v1`
          : `${proto}//${window.location.host}/api/v1`;

        const res = await fetch(`${apiUrl}/auth/github/callback?code=${encodeURIComponent(code)}`, {
          headers: { Accept: "application/json" },
        });

        // If backend returned a redirect or token JSON
        if (res.redirected) {
          window.location.href = res.url;
          return;
        }

        const data = await res.json();

        if (!res.ok) {
          throw new Error(data.detail || data.error || "Failed to exchange authorization code");
        }

        const token = data.access_token || data.token;
        if (token) {
          setAuthToken(token);
          setStatus("success");
          setTimeout(() => {
            window.location.href = "/";
          }, 800);
        } else {
          // If response was 200 but token in URL param
          window.location.href = "/";
        }
      } catch (err: any) {
        setStatus("error");
        setErrorMessage(err.message || "Failed to authenticate with GitHub.");
      }
    }

    handleCallback();
  }, [searchParams]);

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col justify-center items-center p-4">
      <div className="glass max-w-md w-full p-8 rounded-3xl shadow-2xl text-center">
        {status === "loading" && (
          <div className="space-y-4">
            <Loader2 size={40} className="animate-spin text-orange-500 mx-auto" />
            <h2 className="text-xl font-bold text-slate-800">Authenticating with GitHub...</h2>
            <p className="text-sm text-slate-500">Exchanging credentials and preparing your engineering workspace.</p>
          </div>
        )}

        {status === "success" && (
          <div className="space-y-4">
            <CheckCircle2 size={40} className="text-emerald-500 mx-auto" />
            <h2 className="text-xl font-bold text-slate-800">Authentication Successful!</h2>
            <p className="text-sm text-slate-500">Redirecting to your workspace...</p>
          </div>
        )}

        {status === "error" && (
          <div className="space-y-5">
            <div className="w-12 h-12 rounded-full bg-red-100 text-red-600 flex items-center justify-center mx-auto">
              <AlertCircle size={24} />
            </div>
            <div>
              <h2 className="text-xl font-bold text-slate-800 mb-1">Authentication Failed</h2>
              <p className="text-xs text-red-600 bg-red-50 p-3 rounded-xl border border-red-200 break-words mt-2">
                {errorMessage}
              </p>
            </div>
            <Link
              href="/auth"
              className="inline-flex items-center justify-center gap-2 w-full py-2.5 px-4 rounded-xl bg-slate-900 text-white text-sm font-medium hover:bg-slate-800 transition-colors shadow-xs"
            >
              <ArrowLeft size={16} />
              Return to Sign In
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}

export default function GitHubCallbackPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-slate-50 flex flex-col justify-center items-center p-4">
          <div className="glass max-w-md w-full p-8 rounded-3xl shadow-2xl text-center space-y-4">
            <Loader2 size={40} className="animate-spin text-orange-500 mx-auto" />
            <h2 className="text-xl font-bold text-slate-800">Connecting to GitHub...</h2>
          </div>
        </div>
      }
    >
      <GitHubCallbackContent />
    </Suspense>
  );
}
