# Claude desktop app setup (Windows 11): about 10 minutes

This connects the Claude desktop app, signed in with your Pro account, to the tool on your laptop. Claude then fetches the tool's agent tasks and submits its answers directly, with no copy-paste and no API credit (D-31).

**Status: tested here only with a scripted MCP client. Not yet tested in the real Claude desktop app.** Do the first-time check below on one laptop as early as possible. If something differs from these steps, note it and tell the build lead.

## 1. Prerequisites
- The repo set up as in `README.md` (Python 3.12, `.venv`, `pip install -r requirements.txt`).
- The Claude desktop app for Windows, from https://claude.ai/download, signed in with your Pro account.
- If your account is managed by the institute, local connectors may be switched off by the administrator. Step 4 tells you if so.

## 2. Register the connector (once per laptop)
In PowerShell, in the repo folder:
```powershell
.\.venv\Scripts\Activate.ps1
python mcp_server\install_windows.py
```
This adds an `orgfit` entry to `%APPDATA%\Claude\claude_desktop_config.json`, keeps any other entries, and saves a `.bak` backup.

You can also add it by hand: Claude desktop app → Settings → Developer → Edit Config, then add the `orgfit` block the script printed.

## 3. Restart Claude completely
Right-click the Claude icon in the system tray → **Quit**. Open Claude again. Closing the window is not enough.

## 4. First-time check
1. In a new chat, open the tools/connectors menu (the slider or plus icon below the message box) and check that **orgfit** is listed and switched on.
2. Type: `Use orgfit to list the cases.`
3. Claude asks permission to use the tool. Choose **Allow** (or "Allow for this chat"). It should list `T1_coherent_misfit (SYNTHETIC)`.

If orgfit does not appear:
- Check that the config file exists.
- Check Settings → Developer, which shows the connector status and an error log.
- Make sure you quit Claude completely in step 3.

The most common cause is the `.venv` missing the packages: rerun `pip install -r requirements.txt`.

## 5. Running a case
In a new chat:
```
Use orgfit to start a run of T1_coherent_misfit, then process all pending tasks.
```
Claude starts the run, fetches each task, does the extraction or classification, and submits the result. After each submission the tool shows how many quotes were found in the source. Unfound quotes are rejected later and logged. When a stage's tasks are done, the run continues by itself.

**Human checkpoints.** The run stops at CP1, and Claude tells you which file to review. Claude has **no tool** to approve evidence, answer CP2 or choose options at CP3. That is by design (MT Table 11). Do the checkpoint in the file, and later in the Streamlit app. Then type:
```
I have finished CP1. Resume run T1_coherent_misfit/<run id>. My name is <your name>.
```

**Long cases.** Start a new chat after about 5 tasks so Claude's context stays clear. Then type `Use orgfit: list pending tasks for run <run id> and process them.`

## 6. Good practice
- Do not give Claude a file-system connector to the `runs\` folder. The checkpoint files must be edited only by people.
- Real-company sources stay on your laptop. The connector reads them locally, and Claude sees only the chunks inside tasks.
- Usage limits of your Pro plan apply. Split a real firm's tasks across members' laptops if needed: each member can run the same case folder.
- Every answer is stored in `cache\` with the label "Claude via Claude desktop app (local MCP connector)". **Replay mode** (`--mode replay`) reproduces the run without Claude. That is the demo backup.

## Fallback
If the desktop app or your account does not allow local connectors, use paste mode (`--mode paste`, see `agents/README.md`). The tasks and checks are identical.
