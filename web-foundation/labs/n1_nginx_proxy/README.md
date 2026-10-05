# n1 · Nginx 反代实战：流式服务的生死开关

目标：亲手制造并修复流式服务最常见的两类生产事故——**缓冲攒流**与**超时掐流**。

## 前置

```bash
docker pull nginx:1.28-alpine        # 官方 stable 镜像
python -m uvicorn n1_nginx_proxy.app:app --host 0.0.0.0 --port 8807   # 注意必须绑 0.0.0.0
```

> 为什么绑 0.0.0.0：Nginx 跑在容器里，经 `host.docker.internal` 回访宿主机；
> uvicorn 默认只绑 127.0.0.1，会拒绝来自虚拟网卡的连接（502 现场之一）。

## 一键对照实验

```bash
python n1_nginx_proxy/verify_through_nginx.py
```

它做两次部署、同一个后端、同一个 URL：

| 配置 | 现象 |
|---|---|
| `n1-good.conf`（buffering off + read_timeout 3600s） | 10 个事件陆续到达（跨度 ≈ 7s），WebSocket 透传正常 |
| `n1-incident.conf`（read_timeout 2s） | LLM"思考"静默 4 秒 → 连接被 Nginx 掐断 |

## 三个事故机制（配置文件里有逐行注释）

1. **proxy_buffering on**：Nginx 会尽量从上游读取再转发。下游快于上游时影响不大，
   但叠加 gzip/TLS/慢客户端后，SSE 小事件会被攒住——用户看到"卡一下全出来"。
   快api.sse 自动发送 `X-Accel-Buffering: no` 响应头豁免缓冲；
   `n1-incident.conf` 里故意 `proxy_hide_header` 掉它——旧版运维配置不认识这个头，事故就回来了。
2. **proxy_read_timeout**：上游静默超过阈值即掐断。默认 60s；LLM 思考 4 秒本身不可怕，
   可怕的是"静默 4 秒 + 阈值 2s"。心跳（15s 一条注释行）的存在意义就是不断重置这个定时器。
3. **WebSocket Upgrade 头**：握手必须原样透传 `Upgrade`/`Connection` 头，否则升级失败。

## 自测问题

1. 为什么 curl 测试一切正常、浏览器却卡死？（提示：Accept-Encoding: gzip，浏览器会带）
2. `proxy_read_timeout` 的计时器什么时候开始倒数？"上游慢"和"上游静默"哪个会触发它？
3. 容器里的 nginx 怎么访问宿主机上的 uvicorn？生产 Linux 上对应什么写法？

## 延伸

- 生产 nginx 通常还有 gzip 压缩模块——记得把 `text/event-stream` 排除在 gzip_types 之外，
  否则压缩攒数据会让流式变"卡顿"。
