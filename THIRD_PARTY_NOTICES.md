# Nguồn và giấy phép

CleanupTV là giao diện Windows độc lập, không phải bản phát hành chính thức của CleanYourTV.

- Quy trình và các quy tắc trong `catalog.json` tham khảo [Gathin23/cleanyourtv](https://github.com/Gathin23/cleanyourtv), commit `204143007f0bebfb14d6ef001a32e5836b1c90b5`. MIT, Copyright (c) 2026 Gathin. Khi build, source và nguyên giấy phép được giữ trong `.runtime/source/`.
- Launcher và mô-đun thời tiết được build từ source trên cộng phần mở rộng có mã nguồn trong `launcher-overlay/` và công thức `personalize.py`; giữ tên gói `com.gathin.tvhome` và `io.github.sumyabazar1.weather`. Phần mở rộng CleanupTV theo MIT của kho này; không phải bản phát hành chính thức upstream. Mô-đun thời tiết upstream do Sumyabazar1 đóng góp. Font Outfit trong launcher: SIL Open Font License 1.1; xem `launcher/FONT-LICENSE-OFL.txt` trong source tải về.
- Thời tiết và tìm địa điểm: Open-Meteo, địa danh GeoNames, chất lượng không khí CAMS theo mô-đun upstream. Xem [Open-Meteo](https://open-meteo.com/), [địa danh và ghi công](https://open-meteo.com/en/docs/geocoding-api), cùng điều kiện sử dụng tương ứng. Không kèm dữ liệu dự báo trong Git.
- Python portable: Python Software Foundation License; xem các tệp license trong `.runtime/python/` và [python.org](https://docs.python.org/3/license.html).
- ADB/Android SDK: [Android SDK License Agreement](https://developer.android.com/studio/terms). Bản Google phân phối có các thông báo riêng trong gói tải về. Người dùng tự tải từ Google; không kèm binary trong Git.
- Eclipse Temurin JDK: GPLv2 với Classpath Exception; giữ các tệp license trong `.runtime/jdk/`.
- AndroidX/Gradle và phụ thuộc được tải khi build; giữ thông báo và giấy phép gốc. Không tải APK từ trang thứ ba.

## Bảng giá tùy chọn từ bản 0.6

- Nguồn vàng: [BTMC Hà Nội](https://btmc.vn/gia-vang-theo-ngay.html), phần bảng công khai `/Home/BGiaVang`; giữ tên hãng và đơn vị nguồn, không đóng gói dữ liệu tải về.
- Ngoại tệ: [Vietcombank](https://www.vietcombank.com.vn/KHCN/Cong-cu-tien-ich/Ty-gia) và XML do trang này liên kết; yêu cầu tối đa mỗi 15 phút, thưa hơn giới hạn một yêu cầu mỗi 5 phút ghi trong XML.
- Xăng dầu: [Petrolimex](https://petrolimex.com.vn/thong-tin-khach-hang.html), endpoint tìm mặt hàng Published được chính trang dùng để hiển thị bảng giá, Vùng 1/2 và mốc từng mặt hàng.
- Chỉ đọc dữ liệu công khai qua HTTPS, không phân phối mã JavaScript/logo/website của nhà cung cấp. Không khẳng định quyền tái sử dụng thương mại hoặc cam kết API từ các nguồn. Nguồn và điều kiện của nhà cung cấp vẫn áp dụng; xem [ghi chú 0.6](docs/CHANGELOG-0.6.md).
- `org.json:json:20240303` chỉ dùng trong kiểm thử JVM, không kèm vào APK; giữ LICENSE đi cùng thư viện trong cache Gradle. Mã chạy Android dùng `org.json` của hệ điều hành.

## MIT License — CleanYourTV

Copyright (c) 2026 Gathin

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
