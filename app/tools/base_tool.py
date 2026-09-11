import os
import requests

class BaseTool:
    PROVIDERS = ("ollama", "openai", "gemini")
    DEFAULTS = {"ollama": "llama3", "openai": "gpt-4o-mini", "gemini": "gemini-2.0-flash"}

    def __init__(self):
        self.provider    = os.environ.get("LLM_PROVIDER", "ollama").lower()
        self.model       = os.environ.get("LLM_MODEL", "").strip() or self.DEFAULTS.get(self.provider, "llama3")
        self.temperature = float(os.environ.get("LLM_TEMPERATURE", "0.4"))
        self.timeout     = int(os.environ.get("LLM_TIMEOUT", "200"))

        base_url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
        self.ollama_url = base_url.rstrip("/") + "/api/generate"

        self.openai_key = os.environ.get("OPENAI_API_KEY", "")
        self.openai_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1") + "/chat/completions"

        self.gemini_key  = os.environ.get("GEMINI_API_KEY", "")
        self.gemini_base = "https://generativelanguage.googleapis.com/v1beta/models"

        if self.provider not in self.PROVIDERS:
            print(f"[BaseTool] Unknown provider '{self.provider}', falling back to 'ollama'")
            self.provider = "ollama"

        print(f"[BaseTool] Provider={self.provider}  Model={self.model}")

    def call_model(self, system: str, user: str) -> dict | None:
        """Returns {"text": str, "tokens": {"prompt": int, "completion": int, "total": int}} or None."""
        if self.provider == "openai":
            return self._call_openai(system, user)
        if self.provider == "gemini":
            return self._call_gemini(system, user)
        return self._call_ollama(system, user)

    # ── Ollama ──────────────────────────────────────────────────────────
    def _call_ollama(self, system: str, user: str) -> dict | None:
        payload = {
            "model": self.model,
            "system": system,
            "prompt": user,
            "stream": False,
            "options": {
                "num_predict": -1,          # unlimited
                "temperature": self.temperature,
            },
        }
        try:
            r = requests.post(self.ollama_url, json=payload, timeout=self.timeout)
            r.raise_for_status()
            body = r.json()
            prompt_tok     = body.get("prompt_eval_count", 0)
            completion_tok = body.get("eval_count", 0)
            return {
                "text": body.get("response", ""),
                "tokens": {
                    "prompt":     prompt_tok,
                    "completion": completion_tok,
                    "total":      prompt_tok + completion_tok,
                },
            }
        except requests.exceptions.ConnectionError:
            print(f"[Ollama] Cannot connect to {self.ollama_url} — is Ollama running?")
            return None
        except Exception as e:
            print(f"[Ollama] Error: {e}")
            return None

    # ── OpenAI ───────────────────────────────────────────────────────────
    def _call_openai(self, system: str, user: str) -> dict | None:
        if not self.openai_key:
            print("[OpenAI] OPENAI_API_KEY is not set.")
            return None
        headers = {
            "Authorization": f"Bearer {self.openai_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user",   "content": user},
            ],
            "temperature": self.temperature,
        }
        try:
            r = requests.post(self.openai_url, json=payload, headers=headers, timeout=self.timeout)
            r.raise_for_status()
            body  = r.json()
            usage = body.get("usage", {})
            return {
                "text": body["choices"][0]["message"]["content"],
                "tokens": {
                    "prompt":     usage.get("prompt_tokens", 0),
                    "completion": usage.get("completion_tokens", 0),
                    "total":      usage.get("total_tokens", 0),
                },
            }
        except requests.exceptions.HTTPError as e:
            body = e.response.json() if e.response else {}
            print(f"[OpenAI] HTTP {e.response.status_code}: {body.get('error', {}).get('message', e)}")
            return None
        except Exception as e:
            print(f"[OpenAI] Error: {e}")
            return None

    # ── Gemini ───────────────────────────────────────────────────────────
    def _call_gemini(self, system: str, user: str) -> dict | None:
        if not self.gemini_key:
            print("[Gemini] GEMINI_API_KEY is not set.")
            return None
        url = f"{self.gemini_base}/{self.model}:generateContent"
        headers = {"x-goog-api-key": self.gemini_key}
        payload = {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {
                "temperature": self.temperature,
            },
        }
        try:
            r = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
            r.raise_for_status()
            body  = r.json()
            usage = body.get("usageMetadata", {})
            return {
                "text": body["candidates"][0]["content"]["parts"][0]["text"],
                "tokens": {
                    "prompt":     usage.get("promptTokenCount", 0),
                    "completion": usage.get("candidatesTokenCount", 0),
                    "total":      usage.get("totalTokenCount", 0),
                },
            }
        except requests.exceptions.HTTPError as e:
            body = e.response.json() if e.response else {}
            print(f"[Gemini] HTTP {e.response.status_code}: {body.get('error', {}).get('message', e)}")
            return None
        except Exception as e:
            print(f"[Gemini] Error: {e}")
            return None
