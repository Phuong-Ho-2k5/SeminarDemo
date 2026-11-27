# NEON · Cloudflare Workers seminar

**Hiện tại đã tắt web công khai theo yêu cầu.** `workers.dev` và preview URL
đều bị vô hiệu hóa; URL cũ trả HTTP 404. Source, secret và dữ liệu Durable
Object được giữ nguyên. Các kết quả cloud bên dưới là lịch sử trước khi tắt.
Biên bản: `results/cloud/unpublished.json`.

Chạy bằng terminal tại thư mục project:

```powershell
# Thí nghiệm 1: Async waits
.\demo1.ps1
```

```powershell
# Thí nghiệm 2: Distributed State
.\demo2.ps1
```

Mỗi file tự tạo secret local nếu thiếu, khởi động Worker, chạy thí nghiệm rồi
dừng Worker do nó tạo. Không cần mở giao diện hoặc terminal thứ hai. Nếu đã
có đúng Worker local đang chạy, script dùng lại và giữ Worker đó chạy tiếp.
Port bị ứng dụng khác chiếm sẽ báo lỗi, không tự tắt ứng dụng đó.

Cuối mỗi lệnh có bảng **KẾT QUẢ** trực tiếp trong terminal:

- Demo 1: median tuần tự/đồng thời (ms), số mẫu hợp lệ, tỷ lệ hai median và PASS/FAIL.
- Demo 2: bảng bốn trạng thái RAM/SQLite, instance/object ID trước/sau,
  kiểm tra identity và PASS/FAIL toàn bộ kịch bản.

Các giá trị lấy từ lần chạy hiện tại; nếu lỗi thì hiển thị FAIL hoặc chưa có
dữ liệu. Terminal hiển thị tiếng Việt bằng UTF-8; không cần mở CSV/JSON để xem.

Kết quả in ra terminal và lưu riêng:

- Demo 1: `results/local/demo1/async_samples.csv`, `async_summary.json`.
- Demo 2: `results/local/demo2/state_run.json`.

Mỗi thư mục có `launcher_run.json` ghi kết quả chạy và dừng process. Dữ liệu
SQLite vẫn giữ trong `local-state/`. Chạy lần lượt hai file; không deploy cloud.
Máy mới cần cài Node/Python và chạy `npm ci` một lần. Nếu PowerShell chặn
script, dùng `powershell -NoProfile -ExecutionPolicy Bypass -File .\demo1.ps1`
(hoặc `demo2.ps1`); chỉ áp dụng cho process đang chạy, không đổi policy máy.

Hai demo JavaScript chạy trên một Worker và một SQLite-backed Durable Object.
Giao diện HTML/CSS/JavaScript thuần, tiếng Việt. Không cần framework, Python
package, database bên ngoài hoặc dịch vụ trả phí.

**URL cloud cũ (đã tắt):** https://neon-workers-seminar.neon-workers-seminar.workers.dev

**Trạng thái:** đã kiểm tra API, Async waits, restart thật bằng `ctx.abort()`
và thao tác giao diện qua DOM kết hợp HTTP trên URL này. Kiểm tra trực quan
trong trình duyệt còn bị chặn vì môi trường agent không có browser kết nối.
Chi tiết và số liệu cuối cùng: [báo cáo nghiệm thu](docs/verification-report.md).

## 1. Cách dùng giao diện cloud trước khi tắt

Phần này mô tả deployment trước đây. Hiện URL không phục vụ web/API công khai.

1. Mở URL trên. HTML công khai; các API thí nghiệm yêu cầu token.
2. Mở file **`.demo-token` trên máy này bằng trình soạn thảo**, sao chép giá trị
   vào ô **Token điều khiển**, rồi chọn **Kết nối / Đọc trạng thái**.
   File đã được tạo khi cấu hình secret và nằm ngoài source/bundle/results.
   Không gửi token vào chat hoặc đưa vào URL.
3. Demo **Async waits**: chọn **Chạy tuần tự**, rồi **Chạy đồng thời**.
   HTTP status, body và thời gian hoàn tất xuất hiện ở bảng.
4. Chọn **Đo 5 lượt**: warm-up mỗi cách một lần, sau đó 5 cặp đổi thứ tự;
   chờ khoảng 25–35 giây tùy mạng. Median chỉ dùng mẫu hợp lệ. **Tải CSV**
   xuất 10 mẫu đã đo; warm-up được hiển thị nhưng không tính vào median/CSV.
5. Demo **Distributed State**: chọn **Chạy kịch bản** để chạy đủ
   `0/0 → 3/3 → restart → 0/3 → 1/4`, rồi **Tải JSON**.
   Hoặc dùng các nút riêng theo mục 5.

Token chỉ ở bộ nhớ trang, không dùng localStorage/cookie. Refresh làm mất
token; trang chỉ gọi health GET, sau khi nhập lại token mới GET snapshot.
Refresh không tăng hoặc reset counter. Chỉ một người điều khiển counter
trong lúc đo; các client cùng truy cập object `seminar-demo-2`.

## 2. Cài và chạy local

Yêu cầu Node.js **22.12+** (đã thử với 24.19.0), npm, Python **3.10+** và mạng
để cài dependency. Python chỉ dùng standard library.

Chạy từ thư mục chứa `package.json`:

```powershell
npm ci
npm run setup:local
npm run dev
```

Mở `http://127.0.0.1:8787`. Secret local ở `.dev.vars` (khác secret cloud);
mở file bằng editor để nhập token local vào giao diện. Lệnh setup tạo token
ngẫu nhiên nhưng không in token, không ghi đè file đã có.

Trong terminal thứ hai:

```powershell
npm test
npm run test:api
npm run measure
npm run state:verify
npm run test:ui
npm run check
```

Chạy lần lượt các lệnh thay đổi state; không chạy `test:api`, `state:verify`
và `test:ui` đồng thời trên cùng môi trường. `measure` chỉ gọi async GET nên
không thay đổi counter. Các npm script thử local tự đọc `.dev.vars`; không
cần truyền giá trị token qua command line. `check` là dry-run, không deploy.

Wrangler lưu SQLite local trong `./local-state`. Không xóa thư mục này nếu
muốn giữ dữ liệu. Local và cloud có storage riêng. Giữ nguyên Worker name,
class, migration và object name khi deploy lại.

## 3. Đăng nhập và deploy lại

`wrangler.toml` hiện đặt `workers_dev = false` và `preview_urls = false` để
giữ web tắt. Chỉ đổi `workers_dev` thành `true` khi muốn chủ động công khai lại.

```powershell
npm test
npm run check
npx wrangler login
npx wrangler whoami
```

Phiên CLI khác phiên đăng nhập Dashboard trên trình duyệt. Xác nhận đúng
tài khoản trước khi deploy. Có thể kiểm tra subscription bằng lệnh chỉ đọc
sau, thay ACCOUNT_ID bằng ID từ `whoami`:

```powershell
node scripts/cloud_preflight.mjs ACCOUNT_ID
npm run deploy
```

Preflight không thay đổi subscription; nó từ chối nếu phát hiện subscription
Workers trả phí. Lần triển khai này subscription rỗng, không bật gói trả phí.
Cấu hình chỉ có Static Assets và `new_sqlite_classes = ["PersistentCounter"]`.
Workers Free hỗ trợ SQLite Durable Objects; vượt quota Free sẽ bị từ chối,
không phải lý do để nâng cấp tự động.

Khi clone sang máy khác, file token bị ignore nên không có sẵn. Đặt secret
bằng một trong hai cách:

```powershell
# Nhập token của nhóm tại prompt ẩn:
npx wrangler secret put DEMO_TOKEN

# Hoặc tạo/reuse token ngẫu nhiên trong file .demo-token, gửi qua stdin:
python scripts/configure_secret.py --generate
```

Không chạy cả hai cách nếu muốn giữ một token đang dùng. Secret thay đổi sẽ
khiến token cũ trên giao diện bị từ chối. Thiếu secret, API thí nghiệm trả
503 `DEMO_TOKEN_NOT_CONFIGURED`; thiếu/sai bearer token trả 401. Health và
HTML vẫn công khai. Không dùng `wrangler deploy --temporary` thay deployment.

Migration `v1` dành cho project mới này. Không xóa lịch sử migration hoặc
đổi sang `new_classes` (KV backend). Nếu nhập vào Worker khác đã tồn tại,
kiểm tra lịch sử migration của Worker đó trước.

## 4. Đo và kiểm chứng qua HTTPS

Hai lệnh sau hỏi token bằng prompt ẩn nếu chưa có biến môi trường `DEMO_TOKEN`:

```powershell
python scripts/measure_async.py --base-url https://neon-workers-seminar.neon-workers-seminar.workers.dev
python scripts/verify_cloud_state.py --base-url https://neon-workers-seminar.neon-workers-seminar.workers.dev
python scripts/check_api.py --base-url https://neon-workers-seminar.neon-workers-seminar.workers.dev
```

Nếu muốn dùng credential đã tạo trên máy này mà không in ra terminal:

```powershell
$env:DEMO_TOKEN = (Get-Content -Raw -LiteralPath '.demo-token').Trim()
try {
    python scripts/measure_async.py --base-url https://neon-workers-seminar.neon-workers-seminar.workers.dev
    node scripts/check_ui.mjs --base-url https://neon-workers-seminar.neon-workers-seminar.workers.dev
    python scripts/verify_cloud_state.py --base-url https://neon-workers-seminar.neon-workers-seminar.workers.dev
} finally {
    Remove-Item Env:DEMO_TOKEN
}
```

`check_ui.mjs` dùng JSDOM và gọi API thật: kiểm tra các nút, tải CSV/JSON,
refresh, phục hồi khi lỗi và cả tình huống server đã tăng nhưng client mất
response. Đây là test DOM/HTTP, không phải test render trình duyệt/CSP.

Output mặc định phân biệt theo URL:

| File | Nội dung |
|---|---|
| `results/cloud/async_samples.csv` | 10 mẫu thực tế: trial, route, status, total_ms, body_ok, error |
| `results/cloud/async_summary.json` | URL, timestamp, warm-up, valid/invalid count, median và ratio |
| `results/cloud/state_run.json` | Các snapshot, restart response/error, GET polling, từng điều kiện và PASS/FAIL |
| `results/cloud/api_checks.json` | Auth, method guards, body/headers, GET invariance, 20 increment đồng thời |
| `results/cloud/ui_checks.json` | Kết quả DOM/HTTP của giao diện trên cloud |
| `results/cloud/preflight*.json` | Subscription/settings trước và sau deploy; chỉ đọc |
| `results/local/*` | Kết quả chạy trên Wrangler, không phải số liệu cloud |

`--output-dir DUONG_DAN` đổi nơi lưu. Lần chạy sau ghi đè artifact cùng tên;
dùng thư mục khác để lưu nhiều lần đo. Dữ liệu unit test giả lập chỉ nằm
trong thư mục tạm của test, không dùng làm số liệu báo cáo.

Đồng hồ Python dùng `time.perf_counter()`, browser dùng `performance.now()`;
cả hai dừng sau khi đọc hết body. Timeout tổng **15 giây/request**, không
chỉ timeout socket. Lỗi HTTP/body/timeout được lưu lại, không đo bù. GET
kiểm chứng sau restart tối đa **10 lượt**, cách nhau **500 ms**; từng request
vẫn có deadline. Mọi script trả exit code khác 0 khi kiểm tra thất bại.

## 5. Kịch bản trình bày khoảng 5–6 phút

Mở sẵn trang demo và Dashboard Live Logs hoặc `npm run tail`.

1. **Async waits:** xem `src/async-waits.js`; cả hai cách dùng 3 tác vụ ×
   1.000 ms. Chạy hai nút rồi cho xem median từ 5 lượt đã chuẩn bị. Giải thích
   các lời gọi tạo Promise diễn ra trước `await Promise.all`; đây là chờ I/O
   độc lập, không phải phép tính CPU chạy song song.
2. **Distributed State:** bấm **Reset dữ liệu** → `0/0`; bấm **Tăng cả hai**
   ba lần, chờ mỗi response → `3/3`.
3. Bấm **Khởi động lại object** đúng một lần. Giao diện chuyển sang kiểm
   chứng bằng GET. Cần thấy RAM `0`, SQLite `3`, **instance_id mới** và
   **object_id không đổi**. Lỗi 503 của request restart chưa chứng minh gì.
4. Bấm **Tăng cả hai** một lần → `1/4`. Tải JSON, đối chiếu nhãn
   `SEMINAR_RESTART` trong log. Không dùng Reset thay cho restart.

`memoryCounter` nằm trong **cùng Durable Object** với SQLite. Worker chỉ định
tuyến đến object cố định; không gọi biến RAM này là global state của Worker.
`increment()` dùng một SQL `UPDATE … RETURNING`, rồi cập nhật RAM đồng bộ,
không có await chen giữa. Constructor `INSERT OR IGNORE`, không ghi đè state.

Hai frame để ghép vào Beamer ở `slides/demo-frames.tex`. Chưa có Beamer gốc
trong thư mục và máy không có TeX compiler, nên chưa ghép/render deck gốc.

## 6. API và xử lý lỗi

| Route | Method | Xác thực / response |
|---|---|---|
| `/api/health` | GET | Công khai; tên ứng dụng và trạng thái |
| `/api/async/seq` | GET | Bearer; `done\n` sau 3 khoảng chờ nối tiếp |
| `/api/async/parallel` | GET | Bearer; `done\n` sau 3 khoảng chờ chồng nhau |
| `/api/state` | GET | Bearer; snapshot, không thay đổi state |
| `/api/state/increment` | POST | Bearer; tăng RAM và SQLite đúng một lần |
| `/api/state/reset` | POST | Bearer; reset dữ liệu 0/0 |
| `/api/state/restart` | POST | Bearer; `ctx.abort("SEMINAR_RESTART")` |

Snapshot: `memory_value`, `durable_value`, `instance_id`, `object_id`,
`counter_name`. Mọi API response có `Cache-Control: no-store`. Sai method
trả 405 kèm `Allow`; route không có trả 404. Không có demo Streaming.

- **401:** nhập đúng token của môi trường đang mở; local và cloud khác token.
- **503 OBJECT_RESTART_PENDING:** chuyển sang GET đối chiếu snapshot; không
  tự gọi restart lại. Hết vòng polling mà chưa đổi instance thì FAIL.
- **POST tăng timeout/mất response:** trạng thái có thể đã được ghi; bấm
  **Đọc lại** để biết giá trị thật. Không tự tăng lại để bù.
- **403/1010 từ client Python:** đã sửa bằng User-Agent nhận diện
  `NEON-Seminar-Client/1.0`; không tắt xác minh TLS.
- **TLS/DNS ngay sau lần deploy đầu:** subdomain mới có thể chưa sẵn sàng;
  chờ rồi thử health GET. Không kết luận API chạy chỉ vì deploy thành công.
- **Nhiều người cùng dùng token:** counter có thể lệch kịch bản; dừng, lưu
  FAIL và chạy lại có chủ đích sau khi các client khác ngừng thao tác.
- **Quota Free:** dừng và kiểm tra Dashboard; không nâng cấp/bật trả phí.
- **Mất mạng khi thuyết trình:** dùng CSV/JSON đã lưu, ghi rõ đó là lần chạy
  trước. Không thay số liệu bằng kết quả kỳ vọng.

Không log Authorization hoặc request headers. `X-Request-Id` liên kết request
với log route; `SEMINAR_RESTART` là lỗi có chủ đích để kết thúc instance.

Tài liệu chính thức: [Scheduler](https://developers.cloudflare.com/workers/runtime-apis/scheduler/),
[ctx.abort](https://developers.cloudflare.com/durable-objects/api/state/#abort),
[SQLite storage](https://developers.cloudflare.com/durable-objects/api/sqlite-storage-api/),
[Durable Objects Free](https://developers.cloudflare.com/durable-objects/platform/pricing/),
[Static Assets routing](https://developers.cloudflare.com/workers/static-assets/routing/worker-script/).
