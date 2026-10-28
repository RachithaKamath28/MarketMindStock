import importlib.util
import json
import os
import sys
import unittest
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, ROOT)

spec = importlib.util.spec_from_file_location("app_module", os.path.join(ROOT, "app.py"))
app_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app_module)


class FakeOllamaResponse:
    def __init__(self, events):
        self.lines = [json.dumps(event).encode("utf-8") + b"\n" for event in events]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def __iter__(self):
        return iter(self.lines)


class FakeOpenAIResponse:
    def __init__(self, result):
        self.content = json.dumps(result).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return self.content


class OllamaChatStreamTests(unittest.TestCase):
    def run_stream(self, events):
        response = FakeOllamaResponse(events)
        with patch.dict(os.environ, {"AI_PROVIDER": "ollama"}), patch(
            "urllib.request.urlopen", return_value=response
        ) as urlopen:
            output = list(app_module._stream_ollama_chat("question", [], []))
        request = urlopen.call_args.args[0]
        payload = json.loads(request.data)
        return [json.loads(line) for line in output], payload

    def run_openai(self, result):
        response = FakeOpenAIResponse(result)
        with patch.dict(
            os.environ, {"AI_PROVIDER": "openai", "OPENAI_API_KEY": "test-key"}
        ), patch("urllib.request.urlopen", return_value=response) as urlopen:
            answer = app_module._try_llm_chat("question", [], [])
        request = urlopen.call_args.args[0]
        payload = json.loads(request.data)
        return answer, payload

    def test_openai_output_limit_is_not_reported_as_a_complete_answer(self):
        response = FakeOpenAIResponse({
            "choices": [{
                "message": {"content": "Partial answer"},
                "finish_reason": "length",
            }]
        })
        with patch.dict(
            os.environ, {"AI_PROVIDER": "openai", "OPENAI_API_KEY": "test-key"}
        ), patch("urllib.request.urlopen", return_value=response) as urlopen:
            with self.assertRaisesRegex(RuntimeError, "may be incomplete"):
                app_module._try_llm_chat("question", [], [])
        request = urlopen.call_args.args[0]
        payload = json.loads(request.data)
        self.assertEqual(payload["max_tokens"], 1200)

    def test_openai_normal_completion_returns_answer(self):
        answer, _ = self.run_openai({
            "choices": [{
                "message": {"content": "Complete answer"},
                "finish_reason": "stop",
            }]
        })

        self.assertEqual(answer, "Complete answer")

    def test_incomplete_stream_reports_error_and_uses_higher_output_limit(self):
        output, payload = self.run_stream([
            {"message": {"content": "Partial answer"}}
        ])

        self.assertEqual(output[0], {"content": "Partial answer"})
        self.assertIn("error", output[-1])
        self.assertNotIn("done", output[-1])
        self.assertEqual(payload["options"]["num_predict"], 1024)

    def test_output_limit_is_not_reported_as_a_complete_answer(self):
        output, _ = self.run_stream([
            {"message": {"content": "Partial answer"}},
            {"done": True, "done_reason": "length"},
        ])

        self.assertIn("error", output[-1])
        self.assertNotIn("done", output[-1])

    def test_normal_stop_reports_completion(self):
        output, _ = self.run_stream([
            {"message": {"content": "Complete answer"}},
            {"done": True, "done_reason": "stop"},
        ])

        self.assertEqual(output[-1], {"done": True})


if __name__ == "__main__":
    unittest.main()
