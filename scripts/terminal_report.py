"""Readable terminal summaries built only from the experiment's observed data."""


def verdict(value):
    if value is None:
        return 'CHƯA KIỂM TRA'
    return 'PASS' if value else 'FAIL'


def print_async_report(result):
    lines = ['', '=' * 62, 'KẾT QUẢ DEMO 1: ASYNC WAITS', '=' * 62,
             f'{"Cách chạy":<20}{"Mẫu hợp lệ":<16}{"Median (ms)":>18}', '-' * 62]
    total = result.get('trials_per_route', 0)
    for label, route in (('Tuần tự', '/api/async/seq'), ('Đồng thời', '/api/async/parallel')):
        data = result.get('routes', {}).get(route, {})
        median = data.get('median_ms')
        value = f'{median:.3f}' if median is not None else 'Không có mẫu'
        count = f'{data.get("valid_samples", 0)}/{total}'
        lines.append(f'{label:<20}{count:<16}{value:>18}')
    lines.append('-' * 62)
    ratio = result.get('median_speedup')
    lines.append('Tỷ lệ median tuần tự / đồng thời: ' + (f'{ratio:.2f} lần' if ratio is not None else 'chưa đủ dữ liệu'))
    observed = result.get('parallel_faster_observed')
    lines.append('Đồng thời nhanh hơn trong lần đo này: ' +
                 ('chưa đủ dữ liệu' if observed is None else 'CÓ' if observed else 'KHÔNG'))
    lines.append('Thời gian tính đến khi client đọc hết response body.')
    lines.append('Kết luận HTTP/body và số mẫu: ' + verdict(result.get('passed', False)))
    print('\n'.join(lines), flush=True)


def print_state_report(result):
    lines = ['', '=' * 62, 'KẾT QUẢ DEMO 2: DISTRIBUTED STATE', '=' * 62,
             f'{"Trạng thái thực tế":<32}{"RAM":>10}{"SQLite":>12}', '-' * 62]
    for label, key in (('Sau reset', 'after_reset'), ('Trước restart', 'before_restart'),
                       ('Sau restart object', 'after_restart'), ('Tăng tiếp một lần', 'after_increment')):
        snapshot = result.get(key, {})
        lines.append(f'{label:<32}{str(snapshot.get("memory_value", "—")):>10}'
                     f'{str(snapshot.get("durable_value", "—")):>12}')
    lines.append('-' * 62)
    before = result.get('before_restart', {})
    after = result.get('after_restart', {})
    lines.append('instance_id trước: ' + before.get('instance_id', 'chưa có dữ liệu'))
    lines.append('instance_id sau:   ' + after.get('instance_id', 'chưa có dữ liệu'))
    lines.append('object_id trước:   ' + before.get('object_id', 'chưa có dữ liệu'))
    lines.append('object_id sau:     ' + after.get('object_id', 'chưa có dữ liệu'))
    checks = result.get('checks', {})
    lines.append('instance_id đổi: ' + verdict(checks.get('new_instance')))
    lines.append('object_id giữ nguyên: ' + verdict(checks.get('same_object_id')))
    restart = result.get('restart_request')
    if restart:
        lines.append(f'Số lần gửi restart: {restart.get("attempts", "chưa có dữ liệu")}')
        if restart.get('error'):
            lines.append('Request restart có lỗi; kết quả dựa trên snapshot GET đọc lại.')
    if result.get('error'):
        lines.append('Lỗi: ' + result['error'])
    lines.append('Kết luận toàn bộ kịch bản: ' + verdict(result.get('passed', False)))
    print('\n'.join(lines), flush=True)
