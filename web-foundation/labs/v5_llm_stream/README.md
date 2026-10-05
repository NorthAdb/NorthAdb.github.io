# v5 LLM Token Streaming：全链路打通

目标：把"LLM 出 token → async generator → SSE → 浏览器打字机"这条最重要的链路亲手跑通。

## 启动与观察

```bash
python -m uvicorn v5_llm_stream.app:app --port 8805 --reload
```

1. 浏览器打开 `http://127.0.0.1:8805/`，同一段提示词分别点两个按钮，对比"转圈圈"和"打字机"。
2. `curl -N -X POST .../chat/stream` 看原始 SSE：注意最后一个事件是 `event: done` + 裸的 `[DONE]`（对齐 OpenAI 约定）。
3. （可选）设置真实 API 后重启，前端与下游代码零改动：
   ```bash
   export OPENAI_API_KEY=sk-...      # 或任何兼容 OpenAI 协议的服务（OPENAI_BASE_URL）
   export OPENAI_MODEL=gpt-4o-mini
   ```

## 代码流程讲解（app.py）

```
OpenAI SDK / MockLLM            async generator               SSE                    浏览器
stream=True 的 chunk    →    yield ServerSentEvent(token) →  data: {"..."}   →  fetch ReadableStream 解析
                             （事件的"生产者"）            （网络上的形态）        （事件的"消费者"）
```

1. **生产者解耦**：`mock_stream` 与 `openai_stream` 产出**同样的东西**（`ServerSentEvent`），端点函数只管拼接和收尾 `[DONE]`。换供应商 = 换 generator。
2. **`raw_data="[DONE]"`**：`data=` 会被 JSON 编码；`raw_data` 原样发送。LLM 协议里大量哨兵值是裸字符串，这个字段就是为此存在的。
3. **前端为什么用 fetch 而不是 EventSource**：`EventSource` 只支持 GET；LLM 对话要 POST 请求体，所以生产前端普遍用 `fetch + ReadableStream` 手动解析 SSE（index.html 里 30 行就是完整解析器，你已在 v3a 认识每个字段）。

## 自测问题

1. token 事件从 LLM 到用户眼睛，一共经过几层"翻译"？每层的输入输出是什么？
2. 为什么 OpenAI 流式响应最后要发一个 `[DONE]`？没有它客户端怎么知道结束了？
3. 如果 LLM 服务 30 秒不吐 token，这条 SSE 连接会发生什么？（提示：v3c 的心跳；想想 Nginx 默认读超时）
4. `EventSource` 与 `fetch` 流式解析各自适合什么场景？

## 延伸

- [openai-python streaming 文档]；下一课给 token 流加上"RAG 进度、工具调用"等事件——从"流文本"进化到"流过程"。
