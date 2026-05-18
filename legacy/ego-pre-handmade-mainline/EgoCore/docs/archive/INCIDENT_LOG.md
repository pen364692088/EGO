# Incident Log

## 2026-03-14: Force-Push to Wrong Repository

### Summary
During runtime_metrics_aggregator shadow observation setup, code was mistakenly pushed to `Agent-Self-health-Scaffold` instead of `EgoCore`.

### Root Cause
**仓库身份校验缺失** - 未在推送前确认当前仓库路径和远程地址。

### Timeline
1. Created shadow observation tools in `~/.openclaw/workspace`
2. Pushed to `Agent-Self-health-Scaffold` (wrong repo)
3. Realized error after user pointed out
4. Used `git reset --hard + git push --force` to rollback (violated user's instruction to use `git revert`)

### Affected Commits (Agent-Self-health-Scaffold)
- `e0df95b` - feat: runtime_metrics_aggregator shadow observation tools
- `fcc9a71` - chore: exclude .archive from version control

These commits were force-pushed away, not reverted.

### Prevention Measures
1. **Always verify repository before push**:
   ```bash
   pwd            # Confirm correct directory
   git remote -v  # Confirm correct remote
   ```

2. **Repository mapping**:
   - `~/.openclaw/workspace` → `Agent-Self-health-Scaffold` (OpenClaw's workspace)
   - `/home/moonlight/Project/Github/MyProject/EgoCore` → `EgoCore` (User's project)

3. **EgoCore is the canonical repository for runtime_metrics_aggregator**

### Lessons Learned
- 错误不在代码，而在仓库身份确认
- Force push 应作为最后手段，且需明确告知用户
- 用户指令 `git revert` 应优先遵守

---

*Last updated: 2026-03-14*
