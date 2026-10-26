# CleanupTV 0.5.0 — Thanh Tùng Tiên Sinh Cleanup

Ngày 26/10/2026. Bản thử nghiệm; chưa xác minh trên TV thật.

## Cá nhân hóa bằng TV và máy tính

- Mục **Cá nhân hóa TV** trên máy tính: đọc thiết lập thật, xem mô phỏng bố cục, chọn 4–7 cột, lời chào/tên, màu nền, hiệu ứng, độ tối ảnh nền và hiện ngày âm Việt Nam dưới ngày dương. Ngày âm tính tại TV theo UTC+7, không cần Internet; không phải lịch tháng hay lời luận ngày tốt/xấu.
- Cùng các lựa chọn này có trong mục **Cá nhân hóa TV** của launcher, điều khiển bằng remote. Vẫn dùng được khi đã tắt gỡ lỗi. Mở từ nút trong phần Thiết lập launcher hoặc nút mở trên máy tính.
- Đọc cùng bộ SharedPreferences, giữ riêng giá trị thực có/không có để khôi phục chính xác. Không sửa ảnh firmware, cấu hình hình ảnh hoặc âm thanh của TV.
- Không đồng bộ biểu mẫu máy tính liên tục: sau khi chỉnh bằng remote phải bấm Đọc thiết lập lại. Tránh sửa hai nơi cùng lúc hoặc sửa thêm giao diện ở TV khi máy tính đang thử; kiểm tra thấy thay đổi ngoài kế hoạch có thể hoàn tác lần thử.
- Ảnh từ máy tính được thu nhỏ tại trình duyệt, gửi JPEG tối đa 500 KB/Full HD, xác minh byte qua provider trên TV. TV có trình chọn tệp có thể nhập ảnh từ TV/USB; không có trình chọn thì gửi từ máy tính. Tối đa 12 ảnh cá nhân, ảnh đã thêm vẫn được giữ khi hoàn tác lựa chọn.
- Mỗi lần áp dụng từ máy tính tạo bản lưu và thử 3 phút. Bấm Giữ hoặc tự hoàn tác. Chỉnh trực tiếp trên TV là lựa chọn được lưu ngay, có nút **Theo giao diện mặc định**; không có bộ đếm của máy tính khi máy tính không kết nối.

## Thời tiết tùy chọn

- Build/cài mô-đun từ cùng source upstream đã khóa SHA256; có bản dịch tiếng Việt khi TV dùng tiếng Việt. Đây là ứng dụng/ô mở trang thời tiết, không phải nhiệt độ cập nhật liên tục trên Home.
- Chọn thành phố trên TV hoặc tìm bằng máy tính rồi áp dụng trong lần thử. Không tự lấy GPS. Tìm tên qua [Open-Meteo Geocoding](https://open-meteo.com/en/docs/geocoding-api), dữ liệu địa danh GeoNames; mô-đun dùng Open-Meteo cho dự báo và chất lượng không khí. Phụ thuộc khả năng cung cấp dữ liệu và điều kiện sử dụng dịch vụ.
- Launcher không được thêm quyền Internet. Chỉ mô-đun thời tiết có quyền Internet; không thêm quảng cáo/tài khoản cá nhân/analytics. Mô-đun chỉ tải khi mở trang theo cơ chế upstream.
- Cài/cập nhật APK không đổi Home và không xóa dữ liệu ứng dụng. APK đã cài không bị hạ phiên bản/gỡ khi hoàn tác các thiết lập.

## Hỗ trợ TV đã chỉnh bằng công cụ khác

Thông báo sử dụng cách nói có điều kiện, không kết luận rằng người dùng chưa từng dùng chương trình chỉ vì thiếu tệp trên máy:

> Không tìm thấy bản sao lưu của Thanh Tùng Tiên Sinh Cleanup trên máy tính này. Nếu trước đây bạn dùng công cụ khác hoặc đã mất bản lưu, chương trình không thể biết chính xác trạng thái ban đầu. Chỉ hỗ trợ kiểm tra và thử chuyển về Màn hình chính hệ thống còn trên TV; không khôi phục toàn bộ hoặc cài đặt gốc.

- Khi gỡ lỗi đã tắt, người dùng phải bật lại và chấp nhận máy tính trên TV trước. Chương trình không có quyền tự bật từ xa. Rút điện không phải factory reset.
- Chỉ đọc các Home handler mà TV báo là ứng dụng hệ thống, kể cả gói đang tắt; loại thành phần factory/test/setup/recovery. Danh sách này là thông tin do TV cung cấp, không phải khẳng định nhà sản xuất đã kiểm thử ứng dụng đó với CleanupTV.
- Xác minh lại trước khi thử. Người dùng phải chọn và xác nhận giới hạn; tạo bản lưu trạng thái **hiện tại** rồi mới bật đúng gói Home cần thiết, đặt Home, kiểm tra và thử 3 phút.
- Hoàn tác lần hỗ trợ chuyển về Home trước đó thành công rồi mới trả trạng thái gói Home hệ thống về đúng default/enabled/disabled-user/disabled/disabled-until-used đã ghi nhận. Không tắt Home vừa cứu nếu chưa quay lại được Home trước đó.
- Nếu không xác minh Home hiện tại để quay về, chỉ chẩn đoán và hướng dẫn Cài đặt Home của TV; không tự sửa. Gói đã mất, firmware không trả thông tin, TV không boot hoặc mất ADB thì không có cam kết cứu bằng localhost.
- Không bật lại hàng loạt gói, không suy đoán danh sách từ model khác, không tải APK launcher hãng bất kỳ, không root/flash/factory reset. Bản lưu tạo sau sự cố không phục hồi được lịch sử trước đó.

## Build và cập nhật

Các tệp trong `launcher-overlay/` và công thức trong `personalize.py` được áp vào **source nguyên bản đọc lại từ ZIP đã xác minh SHA256** mỗi lần build. Không chạy script cài đặt upstream. Receipt ghi SHA256 APK và hash phần mở rộng; từ chối APK cũ hoặc bị thay đổi. Không phát hành binary trong Git.

Nếu đã cài launcher bản cũ: Giữ/hoàn tác lần thử đang chạy, giữ `.local`, cập nhật source rồi mở START.bat. Trong **Cá nhân hóa TV → Chuẩn bị lần đầu**, xác nhận giấy phép SDK, build launcher, bấm **Sao lưu, cập nhật và thử**, rồi kiểm tra và Giữ. Khác chữ ký APK thì Android có thể từ chối cập nhật; chương trình không tự gỡ ứng dụng để vượt qua. Sau đó mới chỉnh cá nhân hoặc cài mô-đun thời tiết nếu muốn.
