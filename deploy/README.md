# 常驻运行（macOS launchd）

## 先说结论：launchd + Desktop 目录 = 被 TCC 拦住

实测（2026-09-18）：把 `hub/server.py` 交给 LaunchAgent 启动，会立刻崩溃并循环重启：

```
python3: can't open file '/Users/YOU/Desktop/.../hub/server.py': [Errno 1] Operation not permitted
```

原因：**launchd 直接启动的进程不继承终端对「桌面/文稿」文件夹的隐私授权**，
连脚本本身都读不到，更别说读里面的资料。

这跟资料放哪儿无关——只要 `--root` 落在 `~/Desktop` 或 `~/Documents`，都会被拦。
两条出路：

### 方案 A：给 python3 完全磁盘访问权限（推荐，一次设置永久生效）

1. 打开「系统设置 → 隐私与安全性 → 完全磁盘访问权限」
2. 点 `+`，按 `Cmd+Shift+G`，输入 `/usr/bin/python3`，添加并打开开关
3. 然后再装载 LaunchAgent：

```bash
cp deploy/com.example.teaching-hub.plist.template ~/Library/LaunchAgents/com.example.teaching-hub.plist
# 编辑里面的路径（把 /Users/YOU 换成你的家目录）和 Label
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.example.teaching-hub.plist
curl -s http://127.0.0.1:8770/api/ping      # {"ok": true, ...}
```

卸载：

```bash
launchctl bootout gui/$(id -u)/com.example.teaching-hub
```

### 方案 B：把资料和代码都放到非受保护目录

把仓库搬到 `~/Library/Application Support/teaching-hub`、`~/Sites` 或 `~/opt` 之类的位置，
资料根目录也指向那里，就不需要任何额外授权。代价是看不到「桌面」的直观位置。

### 方案 C：不做常驻

就用 `python3 hub/server.py ...` 从终端启动（终端本身已有桌面权限），关掉终端窗口服务就停。

## 排查

```bash
launchctl list | grep teaching-hub          # 第一列是 PID，第二列是上次退出码
tail -20 ~/Library/Logs/teaching-hub.log    # 崩溃原因看这里
```

看到 `Operation not permitted` → 回到方案 A。
看到端口占用 → 先 `pkill -f hub/server.py` 再 bootstrap。

## 提示

`KeepAlive` 用的是 `SuccessfulExit=false`：进程非正常退出才重启；正常退出（比如你手动
`bootout`）不会被拉起来。如果崩溃循环，日志会快速堆积——先 `bootout` 再排查。
