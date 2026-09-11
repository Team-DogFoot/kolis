---
name: check-official-docs-first
description: 라이브러리/API 동작 확인은 임의 테스트·추측 말고 공식문서부터 볼 것. 유저가 반복 강조.
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 72200ebd-0da5-4033-b3ec-f9f88c9623a4
---

동작이 이상하거나 원인을 모를 때, **공식문서를 먼저 읽는다.** 임의로 코드 짜서 때려보거나 "원래 그런가보다"로 넘기지 않는다.

**Why:** 유저가 여러 번 "공식문서 좀 봐라"라고 격하게 지적. 추측→테스트 반복이 시간·돈(RunPod 과금)을 낭비하고 오진을 낳았다 (예: qwen3 thinking이 LiteLLM 연결 문제인데 "thinking 모델은 원래 그래"로 오진, 모델 재다운로드 헛짓).

**How to apply:** ADK는 `adk-docs` MCP([[never-read-typo-inspector]]). LiteLLM·Ollama·기타 라이브러리는 각 공식문서(docs.litellm.ai 등)를 WebFetch로 읽는다. 문서에서 정확한 파라미터·동작을 확인한 뒤 코드를 고친다. 테스트는 문서로 답을 안 뒤 검증용으로만.
