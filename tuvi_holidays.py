# -*- coding: utf-8 -*-
"""
tuvi_holidays.py
=============================================================================
MODULE TỬ VI THỰC CHIẾN & NGÀY LỄ VIỆT NAM (ÂM - DƯƠNG LỊCH)
CHO TRỢ LÝ SU SU
=============================================================================
1. Xem Tử Vi Chuyên Sâu Hàng Ngày Theo Tuổi:
   - Bản Mệnh Lục Thập Hoa Giáp (60 Can Chi & 30 Nạp Âm Ngũ Hành).
   - Tương sinh, tương khắc, tỷ hòa giữa Ngũ Hành Ngày và Bản Mệnh Người Xem.
   - Thập Nhị Kiến Trừ (12 Trực Ngày: Kiến, Trừ, Mãn, Bình, Định, Chấp, Phá, Nguy, Thành, Thâu, Khai, Bế).
   - Nhị Thập Bát Tú (28 Sao chiếu ngày, tính chất Cát/Hung, ứng dụng khởi công, đổ mái, ký hợp đồng).
   - Tam Hợp, Lục Hợp, Lục Xung, Tứ Hành Xung và Tuổi đại kỵ trong ngày.
   - Đánh giá 4 trụ cột vận trình: Công danh - Tài lộc - Quan hệ - An toàn sức khỏe.

2. Hệ Thống Ngày Lễ Việt Nam Toàn Diện:
   - Ngày Lễ Dương Lịch (Tết Tây, 30/4, 1/5, 2/9, 8/3, 20/10, 20/11, v.v.).
   - Ngày Lễ Âm Lịch Truyền Thống (Tết Nguyên Đán, Giỗ Tổ Hùng Vương, Rằm Tháng Giêng, Trung Thu, v.v.).
   - Ngày Sóc (Mùng 1), Ngày Vọng (Rằm 15), Ngày Tam Nương, Ngày Nguyệt Kỵ.
   - Tự động cảnh báo và hiển thị danh sách ngày lễ sắp tới để kỹ sư QS / Chỉ huy trưởng chủ động kế hoạch công trường.
"""

import datetime
from typing import Dict, Any, List, Tuple, Optional
try:
    import tkinter as tk
    from tkinter import ttk, messagebox
except (ImportError, Exception):
    tk = None
    ttk = None
    messagebox = None
try:
    from .lunar_biorhythm import jd_from_date, solar_to_lunar, CAN, CHI
except ImportError:
    from lunar_biorhythm import jd_from_date, solar_to_lunar, CAN, CHI

# =============================================================================
# 1. BẢNG NẠP ÂM LỤC THẬP HOA GIÁP & NGŨ HÀNH (60 CAN CHI)
# =============================================================================

LUC_THAP_HOA_GIAP: Dict[str, Tuple[str, str]] = {
    "Giáp Tý": ("Hải Trung Kim", "Kim"),
    "Ất Sửu": ("Hải Trung Kim", "Kim"),
    "Bính Dần": ("Lư Trung Hỏa", "Hỏa"),
    "Đinh Mão": ("Lư Trung Hỏa", "Hỏa"),
    "Mậu Thìn": ("Đại Lâm Mộc", "Mộc"),
    "Kỷ Tỵ": ("Đại Lâm Mộc", "Mộc"),
    "Canh Ngọ": ("Lộ Bàng Thổ", "Thổ"),
    "Tân Mùi": ("Lộ Bàng Thổ", "Thổ"),
    "Nhâm Thân": ("Kiếm Phong Kim", "Kim"),
    "Quý Dậu": ("Kiếm Phong Kim", "Kim"),
    "Giáp Tuất": ("Sơn Đầu Hỏa", "Hỏa"),
    "Ất Hợi": ("Sơn Đầu Hỏa", "Hỏa"),
    "Bính Tý": ("Giản Hạ Thủy", "Thủy"),
    "Đinh Sửu": ("Giản Hạ Thủy", "Thủy"),
    "Mậu Dần": ("Thành Đầu Thổ", "Thổ"),
    "Kỷ Mão": ("Thành Đầu Thổ", "Thổ"),
    "Canh Thìn": ("Bạch Lạp Kim", "Kim"),
    "Tân Tỵ": ("Bạch Lạp Kim", "Kim"),
    "Nhâm Ngọ": ("Dương Liễu Mộc", "Mộc"),
    "Quý Mùi": ("Dương Liễu Mộc", "Mộc"),
    "Giáp Thân": ("Tuyền Trung Thủy", "Thủy"),
    "Ất Dậu": ("Tuyền Trung Thủy", "Thủy"),
    "Bính Tuất": ("Ốc Thượng Thổ", "Thổ"),
    "Đinh Hợi": ("Ốc Thượng Thổ", "Thổ"),
    "Mậu Tý": ("Tích Lịch Hỏa", "Hỏa"),
    "Kỷ Sửu": ("Tích Lịch Hỏa", "Hỏa"),
    "Canh Dần": ("Tùng Bách Mộc", "Mộc"),
    "Tân Mão": ("Tùng Bách Mộc", "Mộc"),
    "Nhâm Thìn": ("Trường Lưu Thủy", "Thủy"),
    "Quý Tỵ": ("Trường Lưu Thủy", "Thủy"),
    "Giáp Ngọ": ("Sa Trung Kim", "Kim"),
    "Ất Mùi": ("Sa Trung Kim", "Kim"),
    "Bính Thân": ("Sơn Hạ Hỏa", "Hỏa"),
    "Đinh Dậu": ("Sơn Hạ Hỏa", "Hỏa"),
    "Mậu Tuất": ("Bình Địa Mộc", "Mộc"),
    "Kỷ Hợi": ("Bình Địa Mộc", "Mộc"),
    "Canh Tý": ("Bích Thượng Thổ", "Thổ"),
    "Tân Sửu": ("Bích Thượng Thổ", "Thổ"),
    "Nhâm Dần": ("Kim Bạch Kim", "Kim"),
    "Quý Mão": ("Kim Bạch Kim", "Kim"),
    "Giáp Thìn": ("Phúc Đăng Hỏa", "Hỏa"),
    "Ất Tỵ": ("Phúc Đăng Hỏa", "Hỏa"),
    "Bính Ngọ": ("Thiên Hà Thủy", "Thủy"),
    "Đinh Mùi": ("Thiên Hà Thủy", "Thủy"),
    "Mậu Thân": ("Đại Trạch Thổ", "Thổ"),
    "Kỷ Dậu": ("Đại Trạch Thổ", "Thổ"),
    "Canh Tuất": ("Thoa Xuyến Kim", "Kim"),
    "Tân Hợi": ("Thoa Xuyến Kim", "Kim"),
    "Nhâm Tý": ("Tang Đố Mộc", "Mộc"),
    "Quý Sửu": ("Tang Đố Mộc", "Mộc"),
    "Giáp Dần": ("Đại Khê Thủy", "Thủy"),
    "Ất Mão": ("Đại Khê Thủy", "Thủy"),
    "Bính Thìn": ("Sa Trung Thổ", "Thổ"),
    "Đinh Tỵ": ("Sa Trung Thổ", "Thổ"),
    "Mậu Ngọ": ("Thiên Thượng Hỏa", "Hỏa"),
    "Kỷ Mùi": ("Thiên Thượng Hỏa", "Hỏa"),
    "Canh Thân": ("Thạch Lựu Mộc", "Mộc"),
    "Tân Dậu": ("Thạch Lựu Mộc", "Mộc"),
    "Nhâm Tuất": ("Đại Hải Thủy", "Thủy"),
    "Quý Hợi": ("Đại Hải Thủy", "Thủy"),
}

# Ngũ Hành Tương Sinh: A sinh B
NGU_HANH_SINH: Dict[str, str] = {
    "Kim": "Thủy",
    "Thủy": "Mộc",
    "Mộc": "Hỏa",
    "Hỏa": "Thổ",
    "Thổ": "Kim"
}

# Ngũ Hành Tương Khắc: A khắc B
NGU_HANH_KHAC: Dict[str, str] = {
    "Kim": "Mộc",
    "Mộc": "Thổ",
    "Thổ": "Thủy",
    "Thủy": "Hỏa",
    "Hỏa": "Kim"
}

# Lục Hợp Địa Chi
LUC_HOP_MAP = {
    "Tý": "Sửu", "Sửu": "Tý",
    "Dần": "Hợi", "Hợi": "Dần",
    "Mão": "Tuất", "Tuất": "Mão",
    "Thìn": "Dậu", "Dậu": "Thìn",
    "Tỵ": "Thân", "Thân": "Tỵ",
    "Ngọ": "Mùi", "Mùi": "Ngọ"
}

# Tam Hợp Địa Chi
TAM_HOP_GROUPS = [
    {"Thân", "Tý", "Thìn"},
    {"Dần", "Ngọ", "Tuất"},
    {"Hợi", "Mão", "Mùi"},
    {"Tỵ", "Dậu", "Sửu"}
]

# Lục Xung Địa Chi
LUC_XUNG_MAP = {
    "Tý": "Ngọ", "Ngọ": "Tý",
    "Sửu": "Mùi", "Mùi": "Sửu",
    "Dần": "Thân", "Thân": "Dần",
    "Mão": "Dậu", "Dậu": "Mão",
    "Thìn": "Tuất", "Tuất": "Thìn",
    "Tỵ": "Hợi", "Hợi": "Tỵ"
}


# =============================================================================
# 2. THẬP NHỊ KIẾN TRỪ (12 TRỰC NGÀY)
# =============================================================================

TRUC_LIST = [
    ("Kiến", "Cát", "Khởi đầu, gieo mầm", "Tốt cho xuất hành, khai trương, thương thảo ban đầu; kiêng động thổ lớn móng sâu."),
    ("Trừ", "Bình", "Giải trừ, gột rửa", "Tốt cho dỡ bỏ cốp pha cũ, vệ sinh công trường, chữa bệnh, dẹp bỏ tranh chấp hợp đồng."),
    ("Mãn", "Cát", "Đầy đủ, viên mãn", "Tốt cho nhập kho vật tư, thu hồi tiền công nợ, cất nóc, cưới hỏi, tế lễ."),
    ("Bình", "Cát", "Cân bằng, bình hòa", "Tốt cho san nền mặt bằng, lu lèn trải đường, làm móng, bảo dưỡng máy móc cơ giới."),
    ("Định", "Đại Cát", "Ổn định, định đoạt", "Rất tốt cho ký kết hợp đồng dài hạn, chốt thỏa thuận thầu, đổ bê tông sàn móng."),
    ("Chấp", "Bình", "Nắm giữ, bảo tồn", "Tốt cho xây tường, lắp dựng giàn giáo chắc chắn, bóc tách khối lượng; kiêng xuất quỹ lớn."),
    ("Phá", "Hung", "Phá dỡ, thanh lý", "Tốt cho phá dỡ công trình cũ, giải tỏa mặt bằng; kiêng khởi công mới hoặc ký kết."),
    ("Nguy", "Hung", "Nguy hiểm, thử thách", "Đặc biệt chú ý an toàn giàn giáo, mép sàn cao tầng, thiết bị nâng hạ; kiêng mạo hiểm."),
    ("Thành", "Đại Cát", "Thành tựu, thắng lợi", "Rất tốt cho bàn giao công trình, nghiệm thu A-B, thông xe, khai trương dự án, xuất hàng."),
    ("Thâu", "Cát", "Thu hoạch, thu gom", "Tốt cho quyết toán A-B, thu hồi công nợ thầu phụ, gom vật tư tồn kho, nhận chuyển khoản."),
    ("Khai", "Đại Cát", "Khai mở, khởi sự", "Rất tốt cho mở cổng công trường, khai móng, khởi công hạng mục mới, công bố dự án."),
    ("Bế", "Bình", "Đóng lại, cất giữ", "Tốt cho đóng kho niêm phong, kiểm kê cuối tuần, đắp đập, chống thấm; kiêng khai móng mới.")
]


# =============================================================================
# 3. NHỊ THẬP BÁT TÚ (28 SAO CHIẾU NGÀY)
# =============================================================================

NHI_THAP_BAT_TU = [
    # 0 - 6: Đông Phương Thanh Long
    ("Giác", "Mộc Giao", "Bình", "Tốt cho tạo tác, công danh thi cử; kiêng việc mai táng."),
    ("Cang", "Kim Long", "Hung", "Đề phòng tranh chấp pháp lý, cẩn thận kiện tụng hợp đồng, thận trọng khi đi xa."),
    ("Đê", "Thổ Hạc", "Hung", "Kiêng khởi công quy mô lớn, cẩn thận giấy tờ thất lạc."),
    ("Phòng", "Nhật Thỏ", "Đại Cát", "Vạn sự như ý, rất tốt cho khởi công, đổ mái, khai trương, thương thảo hợp đồng."),
    ("Tâm", "Nguyệt Hồ", "Hung", "Dễ nảy sinh bất an, tránh làm việc nguy hiểm trên cao, giữ hòa khí nội bộ."),
    ("Vĩ", "Hỏa Hổ", "Đại Cát", "Thăng quan tiến chức, rất tốt cho khởi công xây dựng, cất nóc, cưới gả."),
    ("Cơ", "Thủy Báo", "Cát", "Tốt cho sửa sang nâng cấp nhà xưởng, nhập kho, chỉnh đốn hồ sơ."),
    # 7 - 13: Bắc Phương Huyền Vũ
    ("Đẩu", "Mộc Giải", "Đại Cát", "Tốt cho khởi tạo, xây đắp công trình, gom tiền bạc, cầu tài lộc."),
    ("Ngưu", "Kim Ngưu", "Hung", "Khó khăn trong luân chuyển dòng tiền; cần kiểm soát chặt định mức hao hụt."),
    ("Nữ", "Thổ Bức", "Hung", "Dễ sinh khẩu thiệt tranh cãi; kiêng ký kết hợp đồng thầu phụ mạo hiểm."),
    ("Hư", "Nhật Thử", "Hung", "Đề phòng hao tài, trễ tiến độ; cần kiểm tra chéo biên bản nghiệm thu."),
    ("Nguy", "Nguyệt Yến", "Hung", "Đề phòng rủi ro an toàn lao động; kiểm tra kỹ dây an toàn và giàn giáo."),
    ("Thất", "Hỏa Trư", "Cát", "Tốt cho đào móng, xây dựng tường bao, thông thương xuất nhập vật tư."),
    ("Bích", "Thủy Du", "Đại Cát", "Trăm sự đều tốt, gia tăng điền sản, thầu xây dựng vinh hiển, ký tá thuận buồm."),
    # 14 - 20: Tây Phương Bạch Hổ
    ("Khuê", "Mộc Lang", "Hung", "Dễ có bất hòa nội bộ; nên kiểm tra kỹ thuật tại hiện trường thay vì tranh luận."),
    ("Lâu", "Kim Cẩu", "Đại Cát", "Rất tốt cho khai trương, giao dịch tài chính, xuất hành công tác, phát lệnh thi công."),
    ("Vị", "Thổ Trĩ", "Đại Cát", "Tốt cho an cư, cất nóc, nhập trạch, ký kết hợp đồng thầu thi công."),
    ("Mão", "Nhật Kê", "Hung", "Kiêng xây dựng ngầm sâu dưới lòng đất; đề phòng mưa bão gây ngập úng."),
    ("Tất", "Nguyệt Ô", "Đại Cát", "Khởi công trăm việc hanh thông, công danh rực rỡ, đối tác tin cậy."),
    ("Chủy", "Hỏa Hầu", "Hung", "Tránh kiện tụng tranh cãi với TVGS; kiêng phá dỡ kết cấu chịu lực nguy hiểm."),
    ("Sâm", "Thủy Viên", "Đại Cát", "Rất tốt cho đàm phán hợp đồng, mở rộng dự án, xây dựng nhà xưởng."),
    # 21 - 27: Nam Phương Chu Tước
    ("Tỉnh", "Mộc Hãn", "Cát", "Tốt cho san lấp mặt bằng, làm đường, đổ bê tông; chú ý phòng cháy chữa cháy."),
    ("Quỷ", "Kim Dương", "Hung", "Kiêng khởi sự dự án mới; chú ý bảo đảm sức khỏe công nhân ca đêm."),
    ("Liễu", "Thổ Chương", "Hung", "Kiêng đào hào sâu, đề phòng sạt trượt đất đá; bảo toàn tài chính."),
    ("Tinh", "Nhật Mã", "Hung", "Đề phòng hao tài tốn của, thất lạc hồ sơ chứng từ; cẩn trọng khi nghiệm thu."),
    ("Trương", "Nguyệt Lộc", "Đại Cát", "Khởi công, tạo tác, thăng tiến sự nghiệp; tiền bạc về tài khoản thuận lợi."),
    ("Dực", "Hỏa Xà", "Cát", "Tốt cho giao lưu, bàn thảo phương án thiết kế; kiêng xuất vốn liều lĩnh."),
    ("Chẩn", "Thủy Dẫn", "Đại Cát", "Rất tốt cho ký kết hợp đồng lớn, bàn giao công trình A-B, xuất hành đại cát.")
]


# =============================================================================
# 4. DANH MỤC CÁC NGÀY LỄ VIỆT NAM (DƯƠNG LỊCH & ÂM LỊCH)
# =============================================================================

SOLAR_HOLIDAYS: Dict[Tuple[int, int], Dict[str, Any]] = {
    (1, 1): {"name": "Tết Dương Lịch (Tết Tây)", "is_major": True, "badge": "🎉 NGHỈ LỄ QUỐC GIA"},
    (9, 1): {"name": "Ngày Truyền thống Học sinh - Sinh viên", "is_major": False, "badge": "🎓 KỶ NIỆM"},
    (3, 2): {"name": "Ngày Thành lập Đảng Cộng sản Việt Nam", "is_major": False, "badge": "⭐ KỶ NIỆM"},
    (14, 2): {"name": "Ngày Lễ Tình Nhân (Valentine)", "is_major": False, "badge": "💖 NGÀY LỄ"},
    (27, 2): {"name": "Ngày Thầy thuốc Việt Nam", "is_major": False, "badge": "🩺 TRI ÂN"},
    (8, 3): {"name": "Ngày Quốc tế Phụ nữ (8/3)", "is_major": False, "badge": "🌸 CHÚC MỪNG PHÁI ĐẸP"},
    (20, 3): {"name": "Ngày Quốc tế Hạnh phúc", "is_major": False, "badge": "😊 QUỐC TẾ"},
    (26, 3): {"name": "Ngày Thành lập Đoàn TNCS Hồ Chí Minh", "is_major": False, "badge": "🔥 TUỔI TRẺ"},
    (30, 4): {"name": "Ngày Giải phóng Miền Nam, Thống nhất Đất nước", "is_major": True, "badge": "🇻🇳 NGHỈ LỄ QUỐC GIA"},
    (30, 4): {"name": "Ngày Giải phóng Miền Nam, Thống nhất Đất nước", "is_major": True, "badge": "🚩 NGHỈ LỄ QUỐC GIA"},
    (1, 5): {"name": "Ngày Quốc tế Lao động", "is_major": True, "badge": "🛠️ NGHỈ LỄ QUỐC GIA"},
    (7, 5): {"name": "Ngày Chiến thắng Điện Biên Phủ", "is_major": False, "badge": "🎖️ CHIẾN THẮNG"},
    (19, 5): {"name": "Ngày sinh Chủ tịch Hồ Chí Minh", "is_major": False, "badge": "⭐ KỶ NIỆM"},
    (1, 6): {"name": "Ngày Quốc tế Thiếu nhi", "is_major": False, "badge": "🎈 THIẾU NHI"},
    (21, 6): {"name": "Ngày Báo chí Cách mạng Việt Nam", "is_major": False, "badge": "📰 BÁO CHÍ"},
    (28, 6): {"name": "Ngày Gia đình Việt Nam", "is_major": False, "badge": "👨‍👩‍👧‍👦 GIA ĐÌNH"},
    (27, 7): {"name": "Ngày Thương binh - Liệt sĩ", "is_major": False, "badge": "🕯️ TRI ÂN"},
    (19, 8): {"name": "Ngày Cách mạng Tháng Tám thành công / CAND", "is_major": False, "badge": "⭐ KỶ NIỆM"},
    (2, 9): {"name": "Ngày Quốc khánh Nước CHXHCN Việt Nam", "is_major": True, "badge": "🇻🇳 NGHỈ LỄ QUỐC GIA"},
    (2, 9): {"name": "Ngày Quốc khánh Nước CHXHCN Việt Nam", "is_major": True, "badge": "🚩 NGHỈ LỄ QUỐC GIA"},
    (10, 10): {"name": "Ngày Giải phóng Thủ đô Hà Nội", "is_major": False, "badge": "🏛️ THỦ ĐÔ"},
    (13, 10): {"name": "Ngày Doanh nhân Việt Nam", "is_major": False, "badge": "💼 DOANH NHÂN"},
    (20, 10): {"name": "Ngày Phụ nữ Việt Nam (20/10)", "is_major": False, "badge": "💐 PHỤ NỮ VN"},
    (20, 11): {"name": "Ngày Nhà giáo Việt Nam", "is_major": False, "badge": "📚 TRI ÂN THẦY CÔ"},
    (22, 12): {"name": "Ngày Thành lập Quân đội Nhân dân Việt Nam", "is_major": False, "badge": "⭐ QUÂN ĐỘI VN"},
    (24, 12): {"name": "Lễ Giáng Sinh (Noel Eve)", "is_major": False, "badge": "🎄 GIÁNG SINH"},
    (25, 12): {"name": "Lễ Giáng Sinh (Noel Chính Ngày)", "is_major": False, "badge": "🎄 GIÁNG SINH"}
}

LUNAR_HOLIDAYS: Dict[Tuple[int, int], Dict[str, Any]] = {
    (1, 1): {"name": "Mùng 1 Tết Nguyên Đán", "is_major": True, "badge": "🧧 TẾT CỔ TRUYỀN"},
    (2, 1): {"name": "Mùng 2 Tết Nguyên Đán", "is_major": True, "badge": "🧧 TẾT CỔ TRUYỀN"},
    (3, 1): {"name": "Mùng 3 Tết Nguyên Đán", "is_major": True, "badge": "🧧 TẾT CỔ TRUYỀN"},
    (4, 1): {"name": "Mùng 4 Tết (Khai Xuân, Xuất Hành)", "is_major": False, "badge": "🎋 KHAI XUÂN"},
    (10, 1): {"name": "Ngày Vía Thần Tài (Đắc Lộc Khai Xuân)", "is_major": False, "badge": "💰 TÀI LỘC"},
    (15, 1): {"name": "Tết Nguyên Tiêu (Rằm Tháng Giêng - Thượng Nguyên)", "is_major": False, "badge": "🏮 NGUYÊN TIÊU"},
    (3, 3): {"name": "Tết Hàn Thực (Bánh trôi, bánh chay)", "is_major": False, "badge": "🍡 HÀN THỰC"},
    (10, 3): {"name": "Ngày Giỗ Tổ Hùng Vương", "is_major": True, "badge": "🇻🇳 QUỐC LỄ NGHỈ"},
    (10, 3): {"name": "Ngày Giỗ Tổ Hùng Vương", "is_major": True, "badge": "🚩 QUỐC LỄ NGHỈ"},
    (15, 4): {"name": "Đại Lễ Phật Đản (Vesak)", "is_major": False, "badge": "🪷 PHẬT ĐẢN"},
    (5, 5): {"name": "Tết Đoan Ngọ (Tết giết sâu bọ)", "is_major": False, "badge": "🍇 ĐOAN NGỌ"},
    (15, 7): {"name": "Lễ Vu Lan Báo Hiếu & Xá Tội Vong Nhân (Rằm Tháng 7)", "is_major": False, "badge": "🕯️ VU LAN"},
    (15, 8): {"name": "Tết Trung Thu (Tết Trông Trăng, Thiếu Nhi)", "is_major": False, "badge": "🥮 TRUNG THU"},
    (9, 9): {"name": "Tết Trùng Cửu", "is_major": False, "badge": "🍵 TRÙNG CỬU"},
    (10, 10): {"name": "Tết Trùng Thập (Hạ Nguyên / Cơm Mới)", "is_major": False, "badge": "🌾 CƠM MỚI"},
    (15, 10): {"name": "Tết Hạ Nguyên (Rằm Tháng Mười)", "is_major": False, "badge": "🌕 HẠ NGUYÊN"},
    (23, 12): {"name": "Tết Táo Quân (Ông Công Ông Táo chầu trời)", "is_major": False, "badge": "🐟 ÔNG TÁO"},
    (30, 12): {"name": "Đêm Giao Thừa (Trừ Tịch)", "is_major": True, "badge": "🎆 GIAO THỪA"}
}


# =============================================================================
# 5. CÁC HÀM TÍNH TOÁN TỬ VI & NGÀY LỄ
# =============================================================================

def get_year_can_chi(year: int) -> Tuple[str, str, str]:
    """Tính Can Chi và Mệnh Nạp Âm của Năm Sinh."""
    can_idx = (year + 6) % 10
    chi_idx = (year + 8) % 12
    can_name = CAN[can_idx]
    chi_name = CHI[chi_idx]
    canchi_str = f"{can_name} {chi_name}"
    nap_am_tuple = LUC_THAP_HOA_GIAP.get(canchi_str, ("Không rõ", "Thổ"))
    return canchi_str, nap_am_tuple[0], nap_am_tuple[1]


def get_tuvi_analysis(birth_date: datetime.date, target_date: datetime.date, person_name: str = "") -> Dict[str, Any]:
    """
    Tính toán phân tích Tử vi hàng ngày chuyên sâu cho người dùng / nhân sự:
    - Bản mệnh người xem
    - Ngũ hành ngày vs Bản mệnh
    - Địa Chi ngày vs Chi Tuổi
    - Trực Ngày (12 Trực)
    - Nhị Thập Bát Tú (28 Sao)
    - Tuổi xung trong ngày
    - Điểm số vận khí và Lời khuyên 4 phương diện thực chiến
    """
    jd = jd_from_date(target_date.day, target_date.month, target_date.year)
    ld, lm, ly, leap = solar_to_lunar(target_date.day, target_date.month, target_date.year)

    # 1. Bản Mệnh Người Xem (Dựa trên năm sinh âm lịch của người đó)
    # Lấy năm sinh âm lịch xấp xỉ
    b_ld, b_lm, b_ly, b_leap = solar_to_lunar(birth_date.day, birth_date.month, birth_date.year)
    user_canchi, user_napam, user_menh = get_year_can_chi(b_ly)

    # 2. Can Chi Ngày & Mệnh Ngày
    can_day_idx = (jd + 9) % 10
    chi_day_idx = (jd + 1) % 12
    can_day = CAN[can_day_idx]
    chi_day = CHI[chi_day_idx]
    day_canchi = f"{can_day} {chi_day}"
    day_napam, day_menh = LUC_THAP_HOA_GIAP.get(day_canchi, ("Bình thường", "Thổ"))

    # 3. Tương Quan Ngũ Hành Ngày & Mệnh Người Xem
    nguhanh_status = ""
    nguhanh_score = 70
    nguhanh_detail = ""

    if NGU_HANH_SINH.get(day_menh) == user_menh:
        nguhanh_status = "Tương Sinh (Đại Cát) 🌟"
        nguhanh_score = 95
        nguhanh_detail = f"Khí vận ngày ({day_menh}) tương sinh bản mệnh của bạn ({user_menh}). Tiếp thêm năng lượng, tài lộc hanh thông, thương thảo dễ đặng."
    elif NGU_HANH_SINH.get(user_menh) == day_menh:
        nguhanh_status = "Sinh Xuất (Thứ Cát) 🌿"
        nguhanh_score = 80
        nguhanh_detail = f"Bản mệnh ({user_menh}) sinh xuất khí ngày ({day_menh}). Cần bỏ ra nhiều công sức và tâm huyết, nhưng kết quả thu về rất xứng đáng."
    elif user_menh == day_menh:
        nguhanh_status = "Tỷ Hòa (Bình Ổn) ⚖️"
        nguhanh_score = 85
        nguhanh_detail = f"Cùng hành ({user_menh}): Thế trận bình hòa, công việc hiện trường diễn ra theo đúng tiến độ kế hoạch đã định."
    elif NGU_HANH_KHAC.get(user_menh) == day_menh:
        nguhanh_status = "Khắc Xuất (Khắc Chế) 🛡️"
        nguhanh_score = 75
        nguhanh_detail = f"Bản mệnh ({user_menh}) khắc chế khí ngày ({day_menh}). Bạn nắm thế chủ động giải quyết vướng mắc, cần kiên trì giám sát đốc thúc tổ đội."
    else:  # day_menh khắc user_menh
        nguhanh_status = "Tương Khắc (Cẩn Trọng) ⚠️"
        nguhanh_score = 60
        nguhanh_detail = f"Khí ngày ({day_menh}) khắc bản mệnh ({user_menh}). Tránh các quyết định bốc đồng, cẩn trọng lời ăn tiếng nói khi họp giao ban với TVGS."

    # 4. Tương Quan Địa Chi (Chi Ngày vs Chi Tuổi)
    user_chi = user_canchi.split()[1]
    chi_status = "Bình hòa"
    chi_badge = "⚖️ BÌNH HÒA"
    chi_score = 70

    if LUC_HOP_MAP.get(user_chi) == chi_day:
        chi_status = f"Lục Hợp Quý Nhân ({user_chi} hợp {chi_day})"
        chi_badge = "🌟 LỤC HỢP"
        chi_score = 95
    elif any(user_chi in grp and chi_day in grp for grp in TAM_HOP_GROUPS):
        chi_status = f"Tam Hợp Cát Khánh ({user_chi} - {chi_day})"
        chi_badge = "✨ TAM HỢP"
        chi_score = 90
    elif LUC_XUNG_MAP.get(user_chi) == chi_day:
        chi_status = f"Trực Xung Đối Kháng ({user_chi} xung {chi_day})"
        chi_badge = "🚨 TRỰC XUNG"
        chi_score = 50
    else:
        chi_status = f"Hòa hợp tự nhiên ({user_chi} và {chi_day})"

    # 5. Thập Nhị Kiến Trừ (12 Trực)
    chi_month_idx = (lm + 1) % 12
    truc_idx = (chi_day_idx - chi_month_idx) % 12
    truc_info = TRUC_LIST[truc_idx]
    truc_name = truc_info[0]
    truc_eval = truc_info[1]
    truc_meaning = truc_info[2]
    truc_advice = truc_info[3]

    # 6. Nhị Thập Bát Tú (28 Sao Chiếu)
    # Công thức chuẩn với offset 11 xác thực theo lịch Hồ Ngọc Đức
    sao_idx = (jd + 11) % 28
    sao_info = NHI_THAP_BAT_TU[sao_idx]
    sao_name = sao_info[0]
    sao_animal = sao_info[1]
    sao_type = sao_info[2]
    sao_desc = sao_info[3]

    # 7. Tuổi Xung Trong Ngày
    xung_chi = LUC_XUNG_MAP.get(chi_day, "")
    xung_can_list = [CAN[(can_day_idx + 4) % 10], CAN[(can_day_idx + 6) % 10]]
    tuoi_xung_ngay = f"{xung_can_list[0]} {xung_chi}, {xung_can_list[1]} {xung_chi}"

    # 8. 4 Trụ Cột Vận Trình Ngày
    overall_tuvi_score = int(round((nguhanh_score * 0.45) + (chi_score * 0.35) + (85 if truc_eval in ["Đại Cát", "Cát"] else 65) * 0.20))
    overall_tuvi_score = max(45, min(99, overall_tuvi_score))

    # Đánh giá chung
    if overall_tuvi_score >= 88:
        rate_text = "Đại Cát Đại Lợi (Vận Khí Rực Rỡ) 🌟🌟🌟"
        rate_col = "#15803d"
    elif overall_tuvi_score >= 75:
        rate_text = "Cát Tường Thuận Lợi (Thiên Thời Địa Lợi) ✨"
        rate_col = "#0369a1"
    elif overall_tuvi_score >= 60:
        rate_text = "Bình Hòa Ổn Định (Vững Bước Tiến Độ) ⚖️"
        rate_col = "#854d0e"
    else:
        rate_text = "Cẩn Trọng Đề Phòng (Bình Tĩnh Thận Trọng) ⚠️"
        rate_col = "#b91c1c"

    # Lời khuyên 4 phương diện
    pillars = {
        "cong_danh": {
            "title": "💼 Công Danh & Tiến Độ",
            "score": min(98, overall_tuvi_score + 2),
            "advice": f"Trực {truc_name} kết hợp Sao {sao_name}: Thích hợp {truc_meaning.lower()}. Hãy rà soát kỹ tiến độ giao ban cuối ngày."
        },
        "tai_loc": {
            "title": "💰 Tài Lộc & Thanh Toán",
            "score": min(98, nguhanh_score),
            "advice": f"Nạp âm {day_napam}: Đốc thúc hồ sơ nghiệm thu A-B, hạn chế phát sinh chi phí ngoài dự toán."
        },
        "quan_he": {
            "title": "🤝 Quan Hệ & Đàm Phán",
            "score": min(98, chi_score),
            "advice": f"{chi_status}. Giữ vững phong thái đĩnh đạc, lắng nghe phản hồi của Chủ đầu tư và Tư vấn giám sát."
        },
        "an_toan": {
            "title": "🛡️ An Toàn & Sức Khỏe",
            "score": max(55, 100 - (100 - overall_tuvi_score) // 2),
            "advice": f"Kiểm tra nghiêm ngặt an toàn mép sàn, giàn giáo và bảo hộ lao động. Tránh làm việc kiệt sức dưới trời nắng gắt."
        }
    }

    return {
        "person_name": person_name or "Tôi",
        "birth_date": birth_date.strftime("%d/%m/%Y"),
        "user_canchi": user_canchi,
        "user_napam": user_napam,
        "user_menh": user_menh,
        "target_date": target_date.strftime("%d/%m/%Y"),
        "day_canchi": day_canchi,
        "day_napam": day_napam,
        "day_menh": day_menh,
        "nguhanh_status": nguhanh_status,
        "nguhanh_detail": nguhanh_detail,
        "chi_status": chi_status,
        "chi_badge": chi_badge,
        "truc_name": truc_name,
        "truc_eval": truc_eval,
        "truc_meaning": truc_meaning,
        "truc_advice": truc_advice,
        "sao_name": sao_name,
        "sao_animal": sao_animal,
        "sao_type": sao_type,
        "sao_desc": sao_desc,
        "tuoi_xung_ngay": tuoi_xung_ngay,
        "overall_score": overall_tuvi_score,
        "rate_text": rate_text,
        "rate_col": rate_col,
        "pillars": pillars
    }


def get_vietnamese_holidays(solar_date: datetime.date) -> Dict[str, Any]:
    """
    Tra cứu ngày lễ Việt Nam cho một ngày cụ thể (cả Dương lịch và Âm lịch),
    kèm danh sách các ngày lễ lớn sắp diễn ra trong 30 ngày tới.
    """
    s_day = solar_date.day
    s_month = solar_date.month
    s_year = solar_date.year

    l_day, l_month, l_year, l_leap = solar_to_lunar(s_day, s_month, s_year)

    today_holidays: List[Dict[str, Any]] = []

    # 1. Kiểm tra ngày lễ Dương lịch
    s_key = (s_day, s_month)
    if s_key in SOLAR_HOLIDAYS:
        h = SOLAR_HOLIDAYS[s_key].copy()
        h["calendar_type"] = "Dương lịch"
        h["date_str"] = f"{s_day:02d}/{s_month:02d}"
        today_holidays.append(h)

    # 2. Kiểm tra ngày lễ Âm lịch
    if not l_leap:
        l_key = (l_day, l_month)
        if l_key in LUNAR_HOLIDAYS:
            h = LUNAR_HOLIDAYS[l_key].copy()
            h["calendar_type"] = "Âm lịch"
            h["date_str"] = f"{l_day:02d}/{l_month:02d} AL"
            today_holidays.append(h)
    else:
        # Tháng nhuận
        if l_day == 1:
            today_holidays.append({"name": f"Mùng 1 Tháng {l_month} (Nhuận)", "is_major": False, "badge": "🌙 NGÀY SÓC", "calendar_type": "Âm lịch", "date_str": f"{l_day:02d}/{l_month:02d} AL (Nhuận)"})
        elif l_day == 15:
            today_holidays.append({"name": f"Rằm Tháng {l_month} (Nhuận)", "is_major": False, "badge": "🌕 NGÀY VỌNG", "calendar_type": "Âm lịch", "date_str": f"{l_day:02d}/{l_month:02d} AL (Nhuận)"})

    # 3. Ngày Sóc (Mùng 1) & Ngày Vọng (Rằm 15) thường kỳ nếu chưa có lễ trùng
    if not today_holidays:
        if l_day == 1:
            today_holidays.append({"name": f"Mùng 1 Đầu Tháng {l_month} Âm Lịch (Ngày Sóc)", "is_major": False, "badge": "🌙 NGÀY SÓC", "calendar_type": "Âm lịch", "date_str": f"01/{l_month:02d} AL"})
        elif l_day == 15:
            today_holidays.append({"name": f"Rằm Tháng {l_month} Âm Lịch (Ngày Vọng)", "is_major": False, "badge": "🌕 NGÀY VỌNG", "calendar_type": "Âm lịch", "date_str": f"15/{l_month:02d} AL"})

    # 4. Ngày Tam Nương & Nguyệt Kỵ
    special_notes = []
    if l_day in [3, 7, 13, 18, 22, 27]:
        special_notes.append("⚠️ Ngày Tam Nương (Mùng 3, 7, 13, 18, 22, 27 AL): Cẩn trọng khởi công, xuất hành xa.")
    if l_day in [5, 14, 23]:
        special_notes.append("⚠️ Ngày Nguyệt Kỵ (Mùng 5, 14, 23 AL): Dân gian có câu 'Mùng năm mười bốn hai ba / Đi chơi cũng thiệt nữa là đi buôn'. Nên cẩn trọng tài chính.")

    # 5. Quét các ngày lễ sắp tới trong vòng 45 ngày
    upcoming: List[Dict[str, Any]] = []
    for d_offset in range(1, 46):
        future_dt = solar_date + datetime.timedelta(days=d_offset)
        f_sd, f_sm, f_sy = future_dt.day, future_dt.month, future_dt.year
        f_ld, f_lm, f_ly, f_leap = solar_to_lunar(f_sd, f_sm, f_sy)

        # Dương
        if (f_sd, f_sm) in SOLAR_HOLIDAYS:
            uh = SOLAR_HOLIDAYS[(f_sd, f_sm)].copy()
            uh["days_left"] = d_offset
            uh["date_solar"] = future_dt.strftime("%d/%m/%Y")
            uh["date_lunar"] = f"{f_ld:02d}/{f_lm:02d} AL"
            upcoming.append(uh)

        # Âm
        if not f_leap and (f_ld, f_lm) in LUNAR_HOLIDAYS:
            uh = LUNAR_HOLIDAYS[(f_ld, f_lm)].copy()
            uh["days_left"] = d_offset
            uh["date_solar"] = future_dt.strftime("%d/%m/%Y")
            uh["date_lunar"] = f"{f_ld:02d}/{f_lm:02d} AL"
            upcoming.append(uh)

    # Sắp xếp ngày lễ tới gần nhất
    upcoming.sort(key=lambda x: x["days_left"])

    is_today_holiday = len(today_holidays) > 0
    is_major_national = any(h.get("is_major", False) for h in today_holidays)

    return {
        "solar_date": solar_date.strftime("%d/%m/%Y"),
        "lunar_date": f"{l_day:02d}/{l_month:02d}/{l_year} AL",
        "is_today_holiday": is_today_holiday,
        "is_major_national": is_major_national,
        "today_holidays": today_holidays,
        "special_notes": special_notes,
        "upcoming_holidays": upcoming[:6]  # 6 ngày lễ gần nhất
    }


def open_tuvi_holidays_popup(parent, birth_date: datetime.date, target_date: datetime.date,
                            person_name: str = "", on_date_select=None):
    """Mở cửa sổ chi tiết Tử Vi Phong Thủy & Tra Cứu Lịch Ngày Lễ Việt Nam."""
    if tk is None:
        print("[TuVi] Tkinter không khả dụng trên môi trường headless/server.")
        return
    win = tk.Toplevel(parent)
    p_name = person_name or "Tôi"
    win.title(f"🔮 Tử Vi Phong Thủy & Lịch Ngày Lễ Việt Nam - {p_name} ({birth_date.strftime('%d/%m/%Y')})")
    win.geometry("900x640")
    win.minsize(800, 540)
    win.configure(bg="#f8fafc")

    tuvi = get_tuvi_analysis(birth_date, target_date, person_name=p_name)
    holidays_info = get_vietnamese_holidays(target_date)

    # Top Toolbar
    top_bar = tk.Frame(win, bg="#0f172a", padx=12, pady=8)
    top_bar.pack(fill=tk.X)

    tk.Label(top_bar, text=f"👤 Hồ sơ: {p_name} (Sinh: {birth_date.strftime('%d/%m/%Y')} - {tuvi['user_canchi']})",
             font=("Segoe UI", 10, "bold"), fg="#38bdf8", bg="#0f172a").pack(side=tk.LEFT)
    tk.Label(top_bar, text=f"📍 Đang xem ngày: {target_date.strftime('%d/%m/%Y')} ({holidays_info['lunar_date']})",
             font=("Segoe UI", 9, "bold"), fg="#f8fafc", bg="#0f172a").pack(side=tk.RIGHT)

    # Notebook Tabs
    nb = ttk.Notebook(win)
    nb.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

    # =========================================================================
    # TAB 1: 🔮 LUẬN GIẢI TỬ VI & BẢN MỆNH THỰC CHIẾN
    # =========================================================================
    f_tuvi = tk.Frame(nb, bg="#f8fafc")
    nb.add(f_tuvi, text="🔮 Luận Giải Tử Vi & Vận Trình")

    c_tuvi = tk.Canvas(f_tuvi, bg="#f8fafc", bd=0, highlightthickness=0)
    sb_tuvi = tk.Scrollbar(f_tuvi, orient="vertical", command=c_tuvi.yview)
    inner_tuvi = tk.Frame(c_tuvi, bg="#f8fafc")

    inner_tuvi.bind("<Configure>", lambda e: c_tuvi.configure(scrollregion=c_tuvi.bbox("all")))
    cw_tuvi = c_tuvi.create_window((0, 0), window=inner_tuvi, anchor="nw")
    c_tuvi.configure(yscrollcommand=sb_tuvi.set)
    c_tuvi.bind("<Configure>", lambda e: c_tuvi.itemconfig(cw_tuvi, width=e.width))

    c_tuvi.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    sb_tuvi.pack(side=tk.RIGHT, fill=tk.Y)

    # Card 1: Bản Mệnh & Ngũ Hành Ngày
    c1 = tk.Frame(inner_tuvi, bg="#ffffff", bd=1, relief=tk.SOLID, padx=12, pady=10)
    c1.pack(fill=tk.X, padx=6, pady=4)

    c1_hdr = tk.Frame(c1, bg="#ffffff")
    c1_hdr.pack(fill=tk.X, pady=(0, 4))
    tk.Label(c1_hdr, text="☯️ TƯƠNG QUAN BẢN MỆNH & KHÍ VẬN NGÀY",
             font=("Segoe UI", 9, "bold"), fg="#0284c7", bg="#ffffff").pack(side=tk.LEFT)
    tk.Label(c1_hdr, text=f"ĐIỂM VẬN KHÍ: {tuvi['overall_score']}/100",
             font=("Segoe UI", 8, "bold"), fg="#ffffff", bg=tuvi['rate_col'], padx=8, pady=1).pack(side=tk.RIGHT)

    tk.Label(c1, text=f"• Bản mệnh người xem: {tuvi['user_canchi']}  |  Nạp âm: {tuvi['user_napam']} (Hành {tuvi['user_menh']})",
             font=("Segoe UI", 9, "bold"), fg="#0f172a", bg="#ffffff", anchor="w").pack(fill=tk.X, pady=1)
    tk.Label(c1, text=f"• Khí vận ngày: {tuvi['day_canchi']}  |  Nạp âm ngày: {tuvi['day_napam']} (Hành {tuvi['day_menh']})",
             font=("Segoe UI", 9), fg="#334155", bg="#ffffff", anchor="w").pack(fill=tk.X, pady=1)

    res_box = tk.Frame(c1, bg="#f1f5f9", padx=8, pady=6, bd=1, relief=tk.SOLID)
    res_box.pack(fill=tk.X, pady=(4, 2))
    tk.Label(res_box, text=f"👉 Đánh giá Ngũ Hành: {tuvi['nguhanh_status']}",
             font=("Segoe UI", 9, "bold"), fg="#0369a1", bg="#f1f5f9", anchor="w").pack(fill=tk.X)
    tk.Label(res_box, text=tuvi['nguhanh_detail'],
             font=("Segoe UI", 8), fg="#334155", bg="#f1f5f9", anchor="w", justify=tk.LEFT, wraplength=780).pack(fill=tk.X, pady=(2, 0))

    # Card 2: Thập Nhị Kiến Trừ (12 Trực) & Nhị Thập Bát Tú (28 Sao)
    c2 = tk.Frame(inner_tuvi, bg="#ffffff", bd=1, relief=tk.SOLID, padx=12, pady=10)
    c2.pack(fill=tk.X, padx=6, pady=4)

    tk.Label(c2, text="📜 THẬP NHỊ KIẾN TRỪ (TRỰC NGÀY) & NHỊ THẬP BÁT TÚ (SAO CHIẾU)",
             font=("Segoe UI", 9, "bold"), fg="#7c3aed", bg="#ffffff", anchor="w").pack(fill=tk.X, pady=(0, 4))

    # Trực
    t_box = tk.Frame(c2, bg="#faf5ff", padx=8, pady=6, bd=1, relief=tk.SOLID)
    t_box.pack(fill=tk.X, pady=2)
    tk.Label(t_box, text=f"👑 Trực ngày: Trực {tuvi['truc_name'].upper()} ({tuvi['truc_eval']}) - {tuvi['truc_meaning']}",
             font=("Segoe UI", 9, "bold"), fg="#6b21a8", bg="#faf5ff", anchor="w").pack(fill=tk.X)
    tk.Label(t_box, text=f"💡 Khuyến nghị công trường: {tuvi['truc_advice']}",
             font=("Segoe UI", 8), fg="#4c1d95", bg="#faf5ff", anchor="w", justify=tk.LEFT, wraplength=780).pack(fill=tk.X, pady=(2, 0))

    # Sao
    s_box = tk.Frame(c2, bg="#f0fdf4", padx=8, pady=6, bd=1, relief=tk.SOLID)
    s_box.pack(fill=tk.X, pady=(4, 2))
    tk.Label(s_box, text=f"⭐ Sao chiếu ngày: Sao {tuvi['sao_name'].upper()} ({tuvi['sao_animal']} - {tuvi['sao_type']})",
             font=("Segoe UI", 9, "bold"), fg="#166534", bg="#f0fdf4", anchor="w").pack(fill=tk.X)
    tk.Label(s_box, text=f"💡 Tính chất sao: {tuvi['sao_desc']}",
             font=("Segoe UI", 8), fg="#14532d", bg="#f0fdf4", anchor="w", justify=tk.LEFT, wraplength=780).pack(fill=tk.X, pady=(2, 0))

    # Card 3: 4 Trụ Cột Vận Trình
    c3 = tk.Frame(inner_tuvi, bg="#ffffff", bd=1, relief=tk.SOLID, padx=12, pady=10)
    c3.pack(fill=tk.X, padx=6, pady=4)

    tk.Label(c3, text="🎯 4 TRỤ CỘT VẬN TRÌNH THỰC CHIẾN HÔM NAY",
             font=("Segoe UI", 9, "bold"), fg="#ca8a04", bg="#ffffff", anchor="w").pack(fill=tk.X, pady=(0, 4))

    grid_p = tk.Frame(c3, bg="#ffffff")
    grid_p.pack(fill=tk.X)

    col_idx = 0
    for p_key, p_val in tuvi['pillars'].items():
        p_frame = tk.Frame(grid_p, bg="#fefce8", bd=1, relief=tk.SOLID, padx=8, pady=6)
        p_frame.grid(row=col_idx // 2, column=col_idx % 2, sticky="nsew", padx=3, pady=3)
        grid_p.grid_columnconfigure(col_idx % 2, weight=1)

        tk.Label(p_frame, text=f"{p_val['title']} ({p_val['score']}/100)",
                 font=("Segoe UI", 8, "bold"), fg="#854d0e", bg="#fefce8", anchor="w").pack(fill=tk.X)
        tk.Label(p_frame, text=p_val['advice'],
                 font=("Segoe UI", 8), fg="#451a03", bg="#fefce8", anchor="w", justify=tk.LEFT, wraplength=360).pack(fill=tk.X, pady=(2, 0))
        col_idx += 1

    # Card 4: Tuổi Xung & Khuyên Căn
    c4 = tk.Frame(inner_tuvi, bg="#fee2e2", bd=1, relief=tk.SOLID, padx=12, pady=8)
    c4.pack(fill=tk.X, padx=6, pady=(4, 8))

    tk.Label(c4, text=f"🚫 TUỔI ĐẠI KỴ TRONG NGÀY: {tuvi['tuoi_xung_ngay']}",
             font=("Segoe UI", 8, "bold"), fg="#991b1b", bg="#fee2e2", anchor="w").pack(fill=tk.X)
    tk.Label(c4, text="Lưu ý: Hạn chế cử nhân sự có tuổi xung phụ trách thương thảo các điều khoản hợp đồng xung đột lớn hoặc ký nghiệm thu có tranh chấp trong ngày này.",
             font=("Segoe UI", 8), fg="#7f1d1d", bg="#fee2e2", anchor="w", justify=tk.LEFT, wraplength=780).pack(fill=tk.X, pady=(2, 0))

    # =========================================================================
    # TAB 2: 🇻🇳 BẢNG TRA CỨU TẤT CẢ NGÀY LỄ VIỆT NAM (ĐẾM NGƯỢC)
    # TAB 2: 🚩 BẢNG TRA CỨU TẤT CẢ NGÀY LỄ VIỆT NAM (ĐẾM NGƯỢC)
    # =========================================================================
    f_holidays = tk.Frame(nb, bg="#ffffff", padx=10, pady=10)
    nb.add(f_holidays, text="🚩 Tra Cứu Ngày Lễ Việt Nam (Đếm Ngược)")

    # Intro Header
    tk.Label(f_holidays, text="🚩 DANH MỤC CÁC NGÀY LỄ LỚN CỦA VIỆT NAM (DƯƠNG LỊCH & ÂM LỊCH)",
             font=("Segoe UI", 10, "bold"), fg="#b91c1c", bg="#ffffff").pack(anchor="w", pady=(0, 4))
    tk.Label(f_holidays, text="Bảng theo dõi giúp Chỉ huy trưởng và Kỹ sư QS nắm bắt chính xác lịch nghỉ lễ quốc gia, ngày truyền thống văn hóa để chủ động tiến độ thi công và chế độ thưởng công trường.",
             font=("Segoe UI", 8), fg="#475569", bg="#ffffff", justify=tk.LEFT).pack(anchor="w", pady=(0, 8))

    # Treeview Table
    cols = ("name", "date_solar", "date_lunar", "type", "countdown", "badge")
    tree = ttk.Treeview(f_holidays, columns=cols, show="headings", height=16)

    tree.heading("name", text="Tên Ngày Lễ")
    tree.heading("date_solar", text="Dương Lịch")
    tree.heading("date_lunar", text="Âm Lịch")
    tree.heading("type", text="Loại Lịch")
    tree.heading("countdown", text="Đếm Ngược")
    tree.heading("badge", text="Tính Chất / Chế Độ")

    tree.column("name", width=260, anchor="w")
    tree.column("date_solar", width=85, anchor="center")
    tree.column("date_lunar", width=85, anchor="center")
    tree.column("type", width=80, anchor="center")
    tree.column("countdown", width=120, anchor="center")
    tree.column("badge", width=160, anchor="center")

    sb_tree = ttk.Scrollbar(f_holidays, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=sb_tree.set)

    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    sb_tree.pack(side=tk.RIGHT, fill=tk.Y)

    # Nạp dữ liệu vào bảng
    # 1. Dương lịch
    for (d, m), info in sorted(SOLAR_HOLIDAYS.items(), key=lambda x: (x[0][1], x[0][0])):
        target_this_year = datetime.date(target_date.year, m, d)
        diff = (target_this_year - target_date).days
        if diff == 0:
            cd_text = "🎉 HÔM NAY"
        elif diff > 0:
            cd_text = f"Còn {diff} ngày"
        else:
            # Sang năm sau
            target_next_year = datetime.date(target_date.year + 1, m, d)
            diff_next = (target_next_year - target_date).days
            cd_text = f"Năm tới ({diff_next} ngày)"

        l_d, l_m, l_y, _ = solar_to_lunar(d, m, target_date.year)
        tree.insert("", tk.END, values=(
            info["name"],
            f"{d:02d}/{m:02d}",
            f"{l_d:02d}/{l_m:02d} AL",
            "Dương lịch",
            cd_text,
            info["badge"]
        ))

    # 2. Âm lịch
    for (ld, lm), info in sorted(LUNAR_HOLIDAYS.items(), key=lambda x: (x[0][1], x[0][0])):
        tree.insert("", tk.END, values=(
            info["name"],
            "—",
            f"{ld:02d}/{lm:02d} AL",
            "Âm lịch",
            "Theo tuần trăng",
            info["badge"]
        ))

