# Bước 8 — Báo cáo phân tích kết quả Day 17

Các số liệu dưới đây được lấy từ một lần chạy sạch bằng `rm -rf state` rồi
`python3 src/benchmark.py`.

| Benchmark | Agent | Agent tokens only | Prompt tokens processed | Cross-session recall | Response quality | Memory growth (bytes) | Compactions |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Standard | Baseline | 1,222 | 12,251 | 0.00 | 0.25 | 0 | 0 |
| Standard | Advanced | 1,475 | 17,802 | 1.00 | 1.00 | 272 | 0 |
| Long-Context Stress | Baseline | 192 | 17,590 | 0.00 | 0.25 | 0 | 0 |
| Long-Context Stress | Advanced | 283 | 9,366 | 1.00 | 1.00 | 221 | 3 |

## 1. Vì sao Advanced có recall tốt hơn Baseline?

Ở cả Standard và Long-Context Stress, `Cross-session recall` của Advanced là
`1.00`, trong khi Baseline là `0.00`; đồng thời Baseline có `Memory growth`
bằng `0` byte. Advanced trích fact ổn định bằng `extract_profile_updates()`,
ghi chúng qua `UserProfileStore.upsert_fact()` vào `state/profiles/<user>/User.md`,
rồi `_offline_response()` đọc profile này khi câu hỏi recall được hỏi bằng một
`thread_id` mới. Đánh đổi là các fact được ghi bền vững có thể trở thành thông
tin sai nếu extractor nhận nhầm một câu nhiễu; vì vậy code chỉ nhận các mẫu
khẳng định cho nghề nghiệp/nơi ở và thay thế fact cũ theo khóa.

## 2. Vì sao Advanced có thể tốn hơn ở hội thoại ngắn?

Ở Standard Benchmark, Advanced sinh `1,475` agent tokens và xử lý `17,802`
prompt tokens, cao hơn Baseline tương ứng `1,222` và `12,251`. Mỗi lượt của
Advanced tải `User.md` rồi cộng profile, summary và recent messages trong
`_estimate_prompt_context_tokens()`; ngoài ra nó còn thực hiện trích và ghi
fact. Giới hạn là 10 lượt hội thoại chuẩn chưa vượt ngưỡng `700` token để
compact chạy (`Compactions = 0`), nên lợi ích giảm context chưa kịp bù chi phí
profile bền vững.

## 3. Vì sao compact có lợi thế ở hội thoại dài?

Trong Long-Context Stress, `Prompt tokens processed` của Advanced là `9,366`,
thấp hơn Baseline `17,590` token, tức giảm khoảng **46.8%**; đồng thời Advanced
có `3` compactions. `CompactMemoryManager.append()` tóm tắt phần message cũ
khi vượt ngưỡng và chỉ giữ nguyên văn các message gần nhất, nên prompt của
lượt sau gồm summary bị chặn kích thước thay vì toàn bộ transcript. Compact
tối ưu **prompt tokens processed**, không mặc định tối ưu `Agent tokens only`:
Advanced vẫn sinh `283` tokens so với `192` của Baseline vì câu trả lời và
profile-recall vẫn phải được tạo ra.

## 4. File memory tăng trưởng ra sao và rủi ro gì?

Advanced tạo profile cuối cùng có kích thước `272` bytes ở Standard và `221`
bytes ở Stress, trong khi Baseline luôn là `0`; Stress cũng xác nhận compact
đã chạy `3` lần. `User.md` chỉ lưu fact ổn định theo các key như `name`,
`location`, `profession` và `response_style`, còn transcript dài đi vào summary
của compact memory, nên profile không phình theo mọi câu chat. Tuy nhiên qua
nhiều user hoặc nhiều fact, file vẫn sẽ tăng và một fact sai có thể tồn tại qua
thread mới; production cần thêm confidence/provenance hoặc memory decay để
kiểm soát rủi ro này.

## Kết luận

Baseline là mốc short-term memory: rẻ hơn ở hội thoại ngắn nhưng quên hoàn toàn
khi đổi thread. Advanced đánh đổi thêm persistent-memory cost để có recall
xuyên phiên, và compact chỉ phát huy rõ trong hội thoại dài bằng cách hạ prompt
load mà không hy sinh các fact bền vững trong `User.md`.
