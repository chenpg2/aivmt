# AIVMT 设备上线 Runbook —— flash + 设备↔服务器↔本地模型 + 真机 QA

> 代码侧已完成并**编译验证**(`idf.py build` GREEN,host FSM 测试 PASS,服务器端点单测通过)。
> 这份清单是**需要你的手 + 真机**的部分。固件 fork 在 `xiaozhi-esp32/`,服务器在 `xiaozhi-esp32-server/`。

## 现状(代码侧,已就绪)
- 固件:persona→OLED、scripted 台词→显示、PTT 按键(Kconfig 门控)、start/stop 听音、transcript 累积(从 stt/tts)、encounter 导出(HTTP POST)。`SpSession` 不再休眠——hook 全部接通。
- 服务器:`POST /aivmt/encounter` 接收并本地归档(去标识、原子写、防路径穿越),已支持本地 Ollama。
- **3 个 on-device 值待你设**(见下),都是配置/真机调,不是写代码。

---

## A. 起本地服务器 + 指向 Ollama(一次)

1. 确认 Ollama 在跑、模型在:
   ```
   ollama serve   # 若未运行
   ollama list | grep llama3.1:8b
   ```
2. 服务器 LLM 指向本地 Ollama(已有配置位):`xiaozhi-esp32-server/main/xiaozhi-server/data/.config.yaml`
   ```
   LLM:
     type: ollama
     base_url: http://localhost:11434
     model_name: llama3.1:8b
   ```
3. 起服务器:
   ```
   cd xiaozhi-esp32-server/main/xiaozhi-server && python app.py
   ```
   - WebSocket(设备对话)默认 `:8000`,HTTP(OTA + `/aivmt/encounter`)默认 `:8003`。
   - 记下本机内网 IP:`ipconfig getifaddr en0`(如 `192.168.31.229`)。
4. encounter 归档目录:默认 `data/aivmt_encounters/`(可用环境变量 `AIVMT_ENCOUNTER_DIR` 改)。

## B. 配置固件三个值(menuconfig)

```
cd xiaozhi-esp32 && source ~/esp/esp-idf/export.sh && idf.py menuconfig
```
在菜单里(或直接改 `sdkconfig`)设:
1. **PTT 按键**:`CONFIG_AIVMT_PTT_ENABLE=y`,`CONFIG_AIVMT_PTT_GPIO=<你接按键的 GPIO>`(bread-compact-wifi 的 BOOT 键是 GPIO0;若复用它注意与板载 OnClick 冲突,建议接一个独立按键)。
2. **encounter 上报 URL**:`CONFIG_AIVMT_ENCOUNTER_POST_URL="http://<本机IP>:8003/aivmt/encounter"`。
3. **设备连服务器**:`sp_config.h` 的 `server_url`(WebSocket)指向 `ws://<本机IP>:8000/xiaozhi/v1/`;Wi-Fi 用设备首次配网流程填。

## C. 编译 + 烧录

```
cd xiaozhi-esp32 && source ~/esp/esp-idf/export.sh
idf.py build
idf.py -p <串口,如 /dev/cu.usbserial-xxxx> flash monitor
```
- 串口:CH340,`ls /dev/cu.*` 找。
- `monitor` 看日志(Ctrl+] 退出)。开机应见 `AIVMT.SpSession: enter Consent`。

## D. 真机 QA(4 项验收 —— 这是"能跑"的证据)

| # | 验收项 | 怎么测 | 通过标准 |
|---|---|---|---|
| QA1 | **PTT 无回声(无硬件 AEC 的关键)** | 按住 PTT 说话时设备正在 TTS 播放 | 松开后 ASR 文本里**没有**把设备自己的话识别进去 |
| QA2 | **OLED persona** | 跑一次问诊 | 屏上显示"[患者 Patient] <label> · <状态>",状态随流程变(Encounter/Feedback) |
| QA3 | **断云离线** | 拔网/防火墙挡公网,只留内网服务器 | 整段问诊仍能完成(本地 Ollama 应答) |
| QA4 | **真实语音 WER** | 录一段真人问诊,比对 ASR 文本与真话 | WER ≤ ~20%(超了说明近场/按键方案要调) |

QA1–QA4 全绿 = 设备能跑一次完整问诊。问诊结束设备会 POST 到 `/aivmt/encounter`,在服务器 `data/aivmt_encounters/` 看到 `<participant>__<case>__<ts>.json`。

## E. 闭环验证(端到端)

1. 服务器在跑(A)。
2. 设备开机 → 输入参与者编号 → 同意 → 病例简介 → **PTT 问诊**(按住说、松开听病人答)→ 说鉴别诊断 → 看反馈。
3. 服务器 `data/aivmt_encounters/` 出现该次 encounter JSON(transcript + telemetry)。
4. 把该 JSON 接入评分管线(与 faculty 评分集同 schema)即可出系统分。

---

## 待你反馈给我的
- QA1–QA4 结果(尤其 WER 实测值)→ 我据此调 PTT/音频时序(`application.integration.patch` 里的 `TODO(on-device)`)。
- 若编译/烧录报错,把 `idf.py build`/`flash` 的最后 ~30 行发我。

代码侧补丁与组件已同步进 `AIVMT/firmware/`(`components/aivmt_sp/`、`main_patches/application.integration.patch`、`server_patches/`),版本可追溯。
