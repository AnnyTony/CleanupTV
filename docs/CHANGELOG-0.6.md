# CleanupTV 0.6 — Bảng giá trên Màn hình chính

Ngày 27/10/2026. Bản thử nghiệm, chưa xác minh bằng TV thật.

## Những gì được thêm

Ba ô tùy chọn nằm dưới phần đồng hồ và trước danh sách ứng dụng: **Giá vàng**, **Tỷ giá ngoại tệ**, **Giá xăng dầu**. Mỗi ô có nguồn, mốc dữ liệu do nguồn công bố và tình trạng tải/bản lưu. Bấm OK bằng remote để xem bảng đầy đủ, thời điểm tải thành công, ngày của từng mặt hàng xăng và địa chỉ nguồn. Các ô chiếm thêm chiều cao; danh sách ứng dụng vẫn cuộn. Chỉ có chữ và nền đơn giản, không nhúng website, video hoặc quảng cáo của nhà cung cấp.

- Vàng: bảng [Bảo Tín Minh Châu tại Hà Nội](https://btmc.vn/gia-vang-theo-ngay.html), gồm nhẫn BTMC 999.9, miếng SJC và trang sức Rồng Thăng Long 999.9. **Giữ nguyên đơn vị nghìn VND do bảng BTMC công bố**, không tự suy đoán/quy đổi chỉ, lượng hoặc thay bằng giá hãng khác. Khi bảng đổi đơn vị, thiếu ngày hoặc thiếu dòng đã rà soát, từ chối dữ liệu mới. Xem tên loại vàng và hỏi nơi giao dịch về quy cách/trọng lượng trước khi dùng giá.
- Ngoại tệ: XML được liên kết từ [Vietcombank](https://www.vietcombank.com.vn/KHCN/Cong-cu-tien-ich/Ty-gia). Phân biệt **mua tiền mặt / mua chuyển khoản / bán ra**, đơn vị VND cho 1 ngoại tệ. Chọn USD, EUR, JPY, AUD, GBP, SGD, THB, CNY, KRW hoặc CAD. Dấu `-` của nguồn được ghi là không niêm yết, không đổi thành 0.
- Xăng dầu: dữ liệu bảng bán lẻ công khai của [Petrolimex](https://petrolimex.com.vn/thong-tin-khach-hang.html), VND/lít. Ưu tiên E10 RON 95-III, E5 RON 92 và DO 0,05S-II khi nguồn còn niêm yết. Giữ đúng tên cấp nhiên liệu, không đổi E10 thành E5. Có Vùng 1/Vùng 2 theo danh mục Petrolimex, không suy ra từ miền Bắc/Nam. Bảng chi tiết giữ mốc LastModified từng sản phẩm; mốc chung là mốc cũ nhất trong các dòng đang hiện, không khẳng định đây là giờ có hiệu lực của quyết định giá.

Giá chỉ tham khảo. Thời điểm TV tải thành công khác với thời điểm nguồn thay đổi giá. Không hiển thị mũi tên tăng/giảm khi chưa có dữ liệu lịch sử so sánh phù hợp. Không điền giá mẫu hoặc đổi sang nguồn khác âm thầm khi lỗi.

## Bật bằng máy tính hoặc remote

1. Nếu đang dùng bản cũ, Giữ hoặc hoàn tác lần thử hiện tại. Giữ thư mục `.local` chứa bản lưu. Build trên cùng tài khoản Windows đã dùng trước đó để giữ khóa ký debug của Android; không xóa khóa ký khi cập nhật.
2. Cập nhật mã nguồn, mở **START.bat → Cá nhân hóa TV → Chuẩn bị lần đầu / cập nhật từ bản cũ**.
3. Build launcher rồi **Sao lưu, cập nhật và thử**. Kiểm tra Home, ứng dụng, remote, HDMI/âm thanh và bấm Giữ. Android có thể từ chối nếu chữ ký APK khác; không tự gỡ launcher để vượt lỗi.
4. Bấm **Đọc thiết lập trên TV**, chọn từng bảng muốn bật, ngoại tệ và vùng xăng, rồi **Thử thiết lập trong 3 phút**. Bấm Giữ khi đã kiểm tra. Hoàn tác trả đúng giá trị trước lần thử, kể cả lựa chọn chưa từng được đặt.
5. Trên TV: **Thiết lập launcher → Cá nhân hóa TV**, bật từng bảng và chọn ngoại tệ/vùng xăng bằng remote. Lưu trực tiếp; có thể tắt lại hoặc dùng Theo giao diện mặc định. Sau khi đã cài và Giữ, không cần máy tính chạy liên tục hay bật gỡ lỗi để bảng hoạt động.

Launcher cũ chưa có khả năng bảng giá sẽ được báo cần cập nhật trong giao diện máy tính. Không cần cài lại mô-đun thời tiết để dùng bảng giá.

## Tải dữ liệu và giới hạn

Mặc định cả ba bảng **tắt**. Launcher 0.6 bổ sung quyền Android `INTERNET`; khác với launcher 0.5 chưa có quyền này. Khi bật, TV truy cập trực tiếp BTMC, Vietcombank và Petrolimex bằng HTTPS, gửi yêu cầu bảng công khai, mã phiên bản ứng dụng và IP kết nối thông thường. Không gửi serial TV, Android ID, model, tên người dùng, vị trí GPS hay dữ liệu tài khoản. Ngoại tệ và vùng được lọc trên TV từ bảng chung, không gửi lựa chọn cá nhân đến nguồn. Không có máy chủ trung gian của CleanupTV, tài khoản hoặc analytics.

Vàng và ngoại tệ kiểm tra tối đa một lượt mỗi 15 phút mỗi nguồn; xăng tối đa một lượt mỗi 6 giờ, kể cả sau lỗi hoặc quay về Home nhiều lần. Chỉ kiểm tra trong lúc Home hoạt động. Khi mở ứng dụng khác, dừng lên lịch/lượt tải mới; yêu cầu đã bắt đầu có thể hoàn tất hoặc hết timeout, kết quả cũ không cập nhật vào màn hình đã đóng. Không có dịch vụ nền, alarm, tự khởi chạy công việc khi đang xem phim hoặc tải trên luồng giao diện.

Một worker cho toàn tiến trình, giới hạn phản hồi 300 KB mỗi nguồn, timeout kết nối/đọc và hạn đọc nội dung. HTTPS giữ kiểm tra chứng chỉ mặc định; không theo redirect sang địa chỉ khác. Địa chỉ nguồn cố định, không nhận URL tùy ý. Dữ liệu HTML chỉ được đọc thành chữ/số, không thực thi script hay hiển thị WebView. Mỗi nguồn được xử lý độc lập; lỗi không ghi đè bản tốt đã lưu. Bảng có dữ liệu cũ ghi rõ bản lưu/chưa cập nhật. Mốc nguồn quá cũ hoặc tương lai được đánh dấu để kiểm tra.

Nhà cung cấp có thể thay cấu trúc, chặn truy cập tự động, thay đổi điều kiện sử dụng hoặc ngừng dịch vụ. Không có cam kết API/SLA từ họ dành cho dự án này; không phải liên kết thương mại hay xác nhận của các hãng. Khi chưa đọc được, chương trình báo lỗi dữ liệu và chờ chu kỳ sau. Nếu ngày giờ TV sai, hãy bật ngày giờ mạng; đồng hồ lùi hoặc chưa hợp lệ sẽ chưa được phép bắt đầu lượt tải mới. Không vượt cơ chế chặn, không tắt xác minh TLS, không tự chuyển sang nguồn thu phí. Nếu dùng để phân phối thương mại cần tự kiểm tra quyền sử dụng dữ liệu với nhà cung cấp.

## Kiểm tra

- Backend: 90 kiểm thử Python qua, gồm giới hạn kiểu/ngoại tệ/vùng và hoàn tác chính xác lựa chọn bảng giá, cùng toàn bộ bộ hồi quy.
- Giao diện máy tính: sửa nút Đọc thiết lập bị giữ trạng thái khóa sau tác vụ/hoàn tác; cập nhật trạng thái điều khiển mà không xóa biểu mẫu đang sửa.
- Android: 15 kiểm thử mới cho đơn vị vàng, dòng/ngày thiếu, ba kiểu tỷ giá, dấu không niêm yết, số sai, XML entity, cấp nhiên liệu, vùng và bộ lọc công khai. Build release, unit test và lint.
- Bộ đọc Java được chạy riêng với phản hồi thật của cả ba nguồn ngày 27/10/2026; không đưa bảng giá tải về vào Git hoặc ZIP.
- Chưa xác minh bố cục 720p/1080p/4K, cỡ chữ lớn, D-pad, chứng chỉ mạng từng firmware hay tải CPU/RAM trên TV thật. Không khẳng định hiệu năng trên tất cả model từ việc build thành công.
