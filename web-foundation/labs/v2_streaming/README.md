# v2 Streaming

目标：亲眼看到"响应可以分块到达"，理解 `async generator + yield` 如何变成 HTTP chunk。

## 启动

```bash
python -m uvicorn v2_streaming.app:app --port 8802 --reload
```

## 实操清单

1. `curl -N -i http://127.0.0.1:8802/slow` —— 3 秒后一次出现完整 JSON。注意响应头里**没有** `content-length`。
2. `curl -N -i http://127.0.0.1:8802/stream` —— 数字一个一个蹦出来（每 0.5s 一个）。
   - 对照实验：去掉 `-N` 再试 → 变成"攒一起"输出。缓冲是客户端和代理都会做的优化，**流式必须显式禁用**。
   - 响应头里能看到 `transfer-encoding: chunked`：HTTP/1.1 分块传输，这就是"流"的字节形态。
3. `curl -N http://127.0.0.1:8802/llm-sim` —— 逐字输出。你已经做出了 ChatGPT 打字机效果的服务端一半。
4. 浏览器 F12 → Network → 请求 `/stream` → EventStream/Response 面板能看到 chunk 陆续到达。

## 代码流程讲解（app.py）

1. `/slow` 是对照组：`return` 的瞬间才构造完整响应体。请求多、生成慢 → 大量连接干等。
2. `number_stream()` 是 async generator。`yield` 一次 = "我这块数据好了"。
3. `StreamingResponse(gen())` 拿到 generator 后：
   - 先发响应头（含 `transfer-encoding: chunked`）；
   - 循环驱动 generator：每次 `yield` → 编码为一个 chunk → 写入 socket；
   - generator 结束（StopAsyncIteration）→ 发终止 chunk，连接收尾。
4. 整个过程中事件循环没有被堵住：`await asyncio.sleep` 让出执行权，别的请求照常处理。**这就是为什么流式必须配异步**。

## 自测问题

1. `-N` 在 curl 里禁用了什么？如果没有它，你还能确认服务端是流式的吗？（提示：F12 Network）
2. `transfer-encoding: chunked` 和 `content-length` 为什么不会同时出现？
3. 如果 generator 里没有 `await`，而是一段纯 CPU 计算 10 秒的循环，事件循环会怎样？

## 延伸

- Starlette StreamingResponse 文档；下一课（v3）你会给这些 chunk 加上"事件"的语义，升级成 SSE。
