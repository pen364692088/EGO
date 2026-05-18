# Request / Reply Lifecycle Notes

## 本轮新增

- turn registry
- request registry
- latest unresolved request lookup
- reply_sent / completed status update on final reply emit

## 当前边界

这还是 v1 骨架，不是完整持久化协议层：
- 目前 registry 仍是进程内内存
- 已能支撑 unresolved request 查询与 reply 归属的宿主骨架
- 下一步应把 registry 持久化并接入 Telegram message_id / turn_id 绑定
