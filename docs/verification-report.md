# Báo cáo triển khai và kiểm chứng thực tế

**Cập nhật trạng thái:** ngày 27/11/2026 đã tắt `workers.dev` và preview URL
theo yêu cầu người dùng; đã kiểm tra URL cũ trả HTTP 404. Dữ liệu và Worker
không bị xóa. Phần bên dưới ghi nhận các lần kiểm chứng trước khi tắt.
Chi tiết: `results/cloud/unpublished.json`.

Ngày chạy: **27/11/2026**. Source và artifact nằm trong project này.

**URL thật:** https://neon-workers-seminar.neon-workers-seminar.workers.dev

Đã triển khai và kiểm chứng chức năng local/cloud. **Chưa ký nghiệm thu toàn
bộ plan:** kiểm tra render trình duyệt thật và ghép/render Beamer gốc còn bị
chặn bởi môi trường/đầu vào. Không coi test JSDOM là test trình duyệt thật.

## Môi trường và deployment

- Windows, PowerShell; Node 24.19.0, npm 11.17.0, Python 3.10.11.
- Wrangler **4.168.0**, khóa bằng `package-lock.json`; `npm ci` đã chạy thành công.
- Worker `neon-workers-seminar`; Static Assets, binding `COUNTER`, class
  `PersistentCounter`, SQLite migration `v1`, object name `seminar-demo-2`.
- API bảo vệ bằng Worker secret `DEMO_TOKEN`. Secret đã được tạo bằng stdin;
  không có giá trị secret trong source, public assets, CSV/JSON hoặc báo cáo.
- Đã kiểm tra subscription bằng Cloudflare API GET trước và sau deploy:
  danh sách subscription rỗng, không có Workers Paid. Không thay subscription
  hoặc kích hoạt sản phẩm trả phí. Xem `results/cloud/preflight*.json`.
- Version đang dùng sau khi đặt secret:
  `6d1358e9-5466-47f4-9cba-db76214f908e`.
  Metadata lấy từ Wrangler ở `results/cloud/deployment.json`.

## Async waits

Đo từ client qua `time.perf_counter()` đến khi đọc hết body. Mỗi môi trường:
warm-up mỗi route một lần, sau đó 5 cặp đổi thứ tự. Mọi mẫu dưới đây trả
HTTP 200 và đúng `done\n`; không có mẫu lỗi hoặc mẫu thay thế.

| Môi trường | Median tuần tự | Median đồng thời | Tỷ lệ hai median | Mẫu hợp lệ |
|---|---:|---:|---:|---:|
| Wrangler local | 3027.237 ms | 1020.118 ms | 2.967536 | 5/5 mỗi cách |
| HTTPS workers.dev | 3234.248 ms | 1208.937 ms | 2.675283 | 5/5 mỗi cách |

Timestamp summary cloud: `2026-11-27T06:43:06.825309+00:00`.
Timestamp summary local: `2026-11-27T06:44:34.527293+00:00`.
Đây là lần chạy cuối bằng client đã sửa deadline tổng. Network/runtime
overhead được giữ trong số đo; không thay bằng 3000/1000 ms lý thuyết.

File gốc: `results/{local,cloud}/async_samples.csv` và
`results/{local,cloud}/async_summary.json`. Script đối chiếu nghiệm thu đã
đọc CSV, kiểm tra thứ tự 10 mẫu và tính lại median độc lập với summary.

## Distributed State: restart object thật

Chạy `scripts/verify_cloud_state.py` trực tiếp trên URL HTTPS nói trên,
timestamp `2026-11-27T06:46:21.658046+00:00`:

| Snapshot | RAM | SQLite |
|---|---:|---:|
| Sau reset | 0 | 0 |
| Trước restart | 3 | 3 |
| Sau restart | 0 | 3 |
| Tăng tiếp một lần | 1 | 4 |

`object_id` trước/sau giữ nguyên:

```text
7276bba874ae418beb1e6415bdec992742a9e8d3a1ac4f2e961264df9b7bfe91
```

`instance_id` đổi:

```text
Trước: dbc20523-0ba0-4da8-9c19-dfb5131e1132
Sau:   a9956fb0-3a3a-415c-87f8-7c84844747a1
```

Request restart được gửi **một lần**, trả HTTP **503** với code
`OBJECT_RESTART_PENDING`. Sau đó script GET snapshot và kiểm tra identity,
RAM, SQLite; lỗi 503 không được dùng làm bằng chứng. Chỉ sau khi đủ điều
kiện script mới POST increment một lần và GET xác nhận `1/4`.

Local cũng kiểm chứng đủ chuỗi trên bằng `ctx.abort()`, không dùng reset
để giả restart. JSON gốc: `results/local/state_run.json` và
`results/cloud/state_run.json`. Wrangler tail cloud thực tế ghi
`SEMINAR_RESTART`; excerpt của một lượt kiểm tra trước đó được lưu riêng
trong `results/cloud/restart-log.txt`. Log excerpt và JSON cuối có thể khác
instance vì chúng thuộc các lượt restart thật khác nhau.

## Kiểm tra tự động

| Kiểm tra | Kết quả | Phạm vi chứng minh |
|---|---|---|
| Node unit tests | 9/9 PASS | Scheduling, auth, body completion, no POST retry, restart polling |
| Python unit/regression tests | 8/8 PASS | Alternation/median, failed samples, restart proof, POST failure, total deadline |
| Real HTTP API local | 57/57 PASS | Routes, token, methods, headers/body, GET invariance, concurrency |
| Real HTTP API cloud | 57/57 PASS | Cùng contract trên HTTPS thật |
| UI DOM + HTTP local | 25/25 PASS | Tất cả nút, benchmark, CSV/JSON, refresh, lỗi/mất response |
| UI DOM + HTTP cloud | 25/25 PASS | Giao diện gọi API deployment; served assets khớp source |
| Missing-secret runtime local | 5/5 PASS | Health 200; API thí nghiệm 503 khi runtime không có secret |
| Dry-run build | PASS | Bundle, binding, migration, assets được Wrangler chấp nhận |
| Cài lại bằng lockfile | PASS | `npm ci` thành công |

API test đã gửi 20 increment đồng thời (5 client threads), nhận đúng tập giá
trị `1..20`, RAM/SQLite khớp và cùng instance/object. Sau đó reset dữ liệu
demo có chủ đích. Test không tự retry increment.

UI test còn mô phỏng **server đã commit increment nhưng response bị mất**:
giao diện báo lỗi, mở lại nút, không gửi increment bù; GET sau đó đọc đúng
giá trị server đã ghi (`2/5` từ state trước đó là `1/4`). Người điều khiển
phải chủ động chạy kịch bản mới nếu muốn bắt đầu lại.

Runtime không-secret dùng cấu hình local riêng `tests/fixtures/no-secret.toml`,
không xóa secret deployment. Test token sai/thiếu được thực hiện trên cloud.

## Lỗi phát hiện và đã xử lý

1. **Subdomain mới chưa sẵn sàng TLS ngay sau deploy:** lần gọi HTTPS đầu
   thất bại với TLS handshake. Kiểm tra lại bằng GET sau khi Cloudflare
   cấp/phổ biến cấu hình đã thành công. Không tắt certificate validation.
2. **HTTP 403/1010 với Python User-Agent mặc định:** đã tái hiện cùng URL
   health: `Python-urllib/3.10` bị 403, `NEON-Seminar-Client/1.0` nhận 200.
   Client dùng nhận diện ứng dụng này; có regression test kiểm tra header.
3. **Socket timeout chưa chặn response kéo dài:** đã tái hiện bằng HTTP
   server local trả từng byte trước khi hết socket timeout. Sửa thành
   deadline tổng 15 giây, đóng transport khi hết hạn, không lặp POST.
   Regression test thực sự gửi POST một lần tới server trả chậm và xác
   nhận client dừng đúng deadline thử nghiệm.

Đã có một lượt code review độc lập; không có lỗi Critical. Lỗi Important về
deadline tổng đã được sửa và kiểm chứng RED → GREEN, rồi chạy lại toàn bộ
unit suite, API tests và phép đo thật.

## Tiêu chí còn bị chặn

1. **Render/kiểm tra trực quan trên trình duyệt thật, CSP thực thi và trình
   duyệt thứ hai:** Browser runtime báo `No browser is available`, danh sách
   browser kết nối rỗng. JSDOM không thay thế được bước này. Cần mở URL bằng
   trình duyệt thật, nhập token và thử các nút/CSV/JSON trên máy trình chiếu.
2. **Ghép và render hai slide vào Beamer gốc:** thư mục đầu vào chỉ có plan,
   không có `demo/` mã khung hoặc source Beamer; không tìm thấy TeX compiler.
   Đã viết đúng hai frame ở `slides/demo-frames.tex`, số liệu và trình tự khớp
   lần chạy cloud. Chưa tuyên bố deck gốc đã được sửa hoặc compile.

`results/acceptance.json` lưu `functional_checks_passed = true` và
`all_plan_criteria_verified = false`, cùng các bước bị chặn. Đây là giới hạn
nghiệm thu thực tế, không phải lỗi chức năng đã được che bằng số liệu giả.
