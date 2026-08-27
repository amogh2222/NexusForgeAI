const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

let globalToken = "";

export function setAuthToken(token: string) {
  globalToken = token;
  if (typeof window !== "undefined") {
    localStorage.setItem("nexusforge_token", token);
  }
}

export function getAuthToken() {
  if (!globalToken && typeof window !== "undefined") {
    globalToken = localStorage.getItem("nexusforge_token") || "";
  }
  return globalToken;
}

async function fetchAPI(endpoint: string, options: RequestInit = {}) {
  const token = getAuthToken();
  const headers = new Headers(options.headers || {});
  
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API_URL}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let errorMsg = await response.text();
    try {
      const json = JSON.parse(errorMsg);
      if (json.detail) errorMsg = typeof json.detail === "string" ? json.detail : JSON.stringify(json.detail);
    } catch (e) {
      // ignore
    }
    
    // Automatically handle expired tokens
    if (response.status === 401) {
      if (typeof window !== "undefined") {
        localStorage.removeItem("nexusforge_token");
        window.location.reload();
      }
    }
    
    throw new Error(errorMsg || `API Error ${response.status}`);
  }

  if (response.status === 204) return null;
  return response.json();
}

export const api = {
  auth: {
    async register(data: any) {
      const response = await fetch(`${API_URL}/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      if (!response.ok && response.status !== 400) {
        throw new Error("Failed to register");
      }
      return response;
    },
    async login(data: any) {
      const response = await fetch(`${API_URL}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      if (!response.ok) throw new Error("Invalid credentials");
      const result = await response.json();
      setAuthToken(result.access_token);
      return result;
    }
  },
  projects: {
    create(data: { name: string, color?: string }) {
      return fetchAPI("/projects/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
    },
    list() {
      return fetchAPI("/projects/");
    }
  },
  repositories: {
    connectGithub(data: { project_id: string, url: string, branch?: string }) {
      return fetchAPI("/repos/github", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
    },
    uploadZip(projectId: string, file: File) {
      const formData = new FormData();
      formData.append("project_id", projectId);
      formData.append("file", file);
      
      const token = getAuthToken();
      return fetch(`${API_URL}/repos/upload`, {
        method: "POST",
        headers: token ? { "Authorization": `Bearer ${token}` } : {},
        body: formData,
      }).then(async (res) => {
        if (!res.ok) throw new Error(await res.text());
        return res.json();
      });
    },
    list(projectId: string) {
      return fetchAPI(`/repos/?project_id=${projectId}`);
    }
  },
  chat: {
    sendMessage(data: { project_id: string, thread_id: string, content: string, repository_id?: string }) {
      return fetchAPI("/chat/message", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
    },
    getHistory(threadId: string) {
      return fetchAPI(`/chat/${threadId}/history`);
    }
  },
  agents: {
    getLogs(projectId: string, limit: number = 50) {
      return fetchAPI(`/agents/logs?project_id=${projectId}&limit=${limit}`);
    }
  },
  intelligence: {
    getSystemDesign(data: { project_id: string, scale: string }) {
      return fetchAPI("/intelligence/system-design", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
    }
  },
  memory: {
    retrieve(projectId: string, query: string, topK: number = 5) {
      return fetchAPI(`/memory/retrieve?project_id=${projectId}&query=${encodeURIComponent(query)}&top_k=${topK}`);
    }
  },
  executions: {
    create(data: { project_id: string, runtime: string, code: string, stdin?: string }) {
      return fetchAPI("/executions/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
    },
    get(executionId: string) {
      return fetchAPI(`/executions/${executionId}`);
    }
  }
};
