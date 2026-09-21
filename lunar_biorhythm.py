"""
lunar_biorhythm.py
=============================================================================
MODULE TÍNH TOÁN LỊCH VẠN NIÊN (ÂM DƯƠNG LỊCH CHUẨN HỒ NGỌC ĐỨC)
VÀ NHỊP SINH HỌC (BIORHYTHM) THỰC CHIẾN CHO TRỢ LÝ SU SU
=============================================================================
1. Lịch Vạn Niên:
   - Chuyển đổi Dương lịch <-> Âm lịch chuẩn xác (múi giờ VN UTC+7).
   - Can Chi của Ngày, Tháng, Năm, Giờ.
   - 24 Tiết Khí chính xác theo kinh độ Mặt Trời.
   - Giờ Hoàng Đạo & Hắc Đạo trong ngày (phục vụ khởi công, đổ bê tông, cất nóc).
   - Hướng xuất hành (Hỷ Thần, Tài Thần).
   - Đánh giá ngày tốt / nên làm / kiêng cữ cho kỹ sư công trường & chỉ huy trưởng.
2. Nhịp Sinh Học:
   - Thể chất (23 ngày), Cảm xúc (28 ngày), Trí tuệ (33 ngày), Trực giác (38 ngày).
   - Cảnh báo Ngày tới hạn (Critical Day) khi qua trục 0.
   - Phân tích và đưa ra lời khuyên thực chiến hàng ngày cho CHT / Kỹ sư QS.
"""

import math
import datetime
from typing import Dict, Any, List, Tuple, Optional

PI = math.pi

# Bảng Can & Chi
CAN = ["Giáp", "Ất", "Bính", "Đinh", "Mậu", "Kỷ", "Canh", "Tân", "Nhâm", "Quý"]
CHI = ["Tý", "Sửu", "Dần", "Mão", "Thìn", "Tỵ", "Ngọ", "Mùi", "Thân", "Dậu", "Tuất", "Hợi"]

# 24 Tiết khí
TIET_KHI = [
    "Xuân Phân", "Thanh Minh", "Cốc Vũ", "Lập Hạ", "Tiểu Mãn", "Mang Chủng",
    "Hạ Chí", "Tiểu Thử", "Đại Thử", "Lập Thu", "Xử Thử", "Bạch Lộ",
    "Thu Phân", "Hàn Lộ", "Sương Giáng", "Lập Đông", "Tiểu Tuyết", "Đại Tuyết",
    "Đông Chí", "Tiểu Hàn", "Đại Hàn", "Lập Xuân", "Vũ Thủy", "Kinh Trập"
]

# Giờ Hoàng Đạo theo Chi của Ngày
HOANG_DAO_DICT = {
    # Tý, Ngọ: Tý, Sửu, Mão, Ngọ, Thân, Dậu
    0: [(0, "Tý (23h-1h)"), (1, "Sửu (1h-3h)"), (3, "Mão (5h-7h)"), (6, "Ngọ (11h-13h)"), (8, "Thân (15h-17h)"), (9, "Dậu (17h-19h)")],
    6: [(0, "Tý (23h-1h)"), (1, "Sửu (1h-3h)"), (3, "Mão (5h-7h)"), (6, "Ngọ (11h-13h)"), (8, "Thân (15h-17h)"), (9, "Dậu (17h-19h)")],
    # Sửu, Mùi: Dần, Mão, Tỵ, Thân, Tuất, Hợi
    1: [(2, "Dần (3h-5h)"), (3, "Mão (5h-7h)"), (5, "Tỵ (9h-11h)"), (8, "Thân (15h-17h)"), (10, "Tuất (19h-21h)"), (11, "Hợi (21h-23h)")],
    7: [(2, "Dần (3h-5h)"), (3, "Mão (5h-7h)"), (5, "Tỵ (9h-11h)"), (8, "Thân (15h-17h)"), (10, "Tuất (19h-21h)"), (11, "Hợi (21h-23h)")],
    # Dần, Thân: Tý, Sửu, Thìn, Tỵ, Mùi, Tuất
    2: [(0, "Tý (23h-1h)"), (1, "Sửu (1h-3h)"), (4, "Thìn (7h-9h)"), (5, "Tỵ (9h-11h)"), (7, "Mùi (13h-15h)"), (10, "Tuất (19h-21h)")],
    8: [(0, "Tý (23h-1h)"), (1, "Sửu (1h-3h)"), (4, "Thìn (7h-9h)"), (5, "Tỵ (9h-11h)"), (7, "Mùi (13h-15h)"), (10, "Tuất (19h-21h)")],
    # Mão, Dậu: Tý, Dần, Mão, Ngọ, Mùi, Dậu
    3: [(0, "Tý (23h-1h)"), (2, "Dần (3h-5h)"), (3, "Mão (5h-7h)"), (6, "Ngọ (11h-13h)"), (7, "Mùi (13h-15h)"), (9, "Dậu (17h-19h)")],
    9: [(0, "Tý (23h-1h)"), (2, "Dần (3h-5h)"), (3, "Mão (5h-7h)"), (6, "Ngọ (11h-13h)"), (7, "Mùi (13h-15h)"), (9, "Dậu (17h-19h)")],
    # Thìn, Tuất: Dần, Thìn, Tỵ, Thân, Dậu, Hợi
    4: [(2, "Dần (3h-5h)"), (4, "Thìn (7h-9h)"), (5, "Tỵ (9h-11h)"), (8, "Thân (15h-17h)"), (9, "Dậu (17h-19h)"), (11, "Hợi (21h-23h)")],
    10: [(2, "Dần (3h-5h)"), (4, "Thìn (7h-9h)"), (5, "Tỵ (9h-11h)"), (8, "Thân (15h-17h)"), (9, "Dậu (17h-19h)"), (11, "Hợi (21h-23h)")],
    # Tỵ, Hợi: Sửu, Thìn, Ngọ, Mùi, Tuất, Hợi
    5: [(1, "Sửu (1h-3h)"), (4, "Thìn (7h-9h)"), (6, "Ngọ (11h-13h)"), (7, "Mùi (13h-15h)"), (10, "Tuất (19h-21h)"), (11, "Hợi (21h-23h)")],
    11: [(1, "Sửu (1h-3h)"), (4, "Thìn (7h-9h)"), (6, "Ngọ (11h-13h)"), (7, "Mùi (13h-15h)"), (10, "Tuất (19h-21h)"), (11, "Hợi (21h-23h)")]
}

# Hướng xuất hành theo Can Ngày
HY_THANH = {
    0: "Đông Bắc", 5: "Đông Bắc",  # Giáp, Kỷ
    1: "Tây Bắc", 6: "Tây Bắc",    # Ất, Canh
    2: "Tây Nam", 7: "Tây Nam",    # Bính, Tân
    3: "Chính Nam", 8: "Chính Nam",# Đinh, Nhâm
    4: "Đông Nam", 9: "Đông Nam"   # Mậu, Quý
}

TAI_THANH = {
    0: "Đông Nam", 1: "Đông Nam",  # Giáp, Ất
    2: "Chính Đông", 3: "Chính Đông", # Bính, Đinh
    4: "Chính Bắc",                # Mậu
    5: "Chính Nam",                # Kỷ
    6: "Tây Nam", 7: "Tây Nam",    # Canh, Tân
    8: "Chính Tây",                # Nhâm
    9: "Chính Bắc"                 # Quý
}


# =============================================================================
# THUẬT TOÁN THIÊN VĂN LỊCH ÂM DƯƠNG HỒ NGỌC ĐỨC
# =============================================================================

def jd_from_date(dd: int, mm: int, yy: int) -> int:
    a = (14 - mm) // 12
    y = yy + 4800 - a
    m = mm + 12 * a - 3
    jd = dd + (153 * m + 2) // 5 + 365 * y + y // 4 - y // 100 + y // 400 - 32045
    if jd < 2299161:
        jd = dd + (153 * m + 2) // 5 + 365 * y + y // 4 - 32083
    return jd


def jd_to_date(jd: int) -> Tuple[int, int, int]:
    if jd > 2299160:
        a = jd + 32044
        b = (4 * a + 3) // 146097
        c = a - (b * 146097) // 4
    else:
        b = 0
        c = jd + 32082
    d = (4 * c + 3) // 1461
    e = c - (1461 * d) // 4
    m = (5 * e + 2) // 153
    day = e - (153 * m + 2) // 5 + 1
    month = m + 3 - 12 * (m // 10)
    year = b * 100 + d - 4800 + (m // 10)
    return day, month, year


def new_moon(k: int) -> float:
    T = k / 1236.85
    T2 = T * T
    T3 = T2 * T
    dr = PI / 180.0
    Jd1 = 2415020.75933 + 29.53058868 * k + 0.0001178 * T2 - 0.000000155 * T3
    Jd1 += 0.00033 * math.sin((166.56 + 132.87 * T - 0.009173 * T2) * dr)
    m = 359.2242 + 29.10535608 * k - 0.0000333 * T2 - 0.00000347 * T3
    Mpr = 306.0253 + 385.81691806 * k + 0.0107306 * T2 + 0.00001236 * T3
    F = 21.2964 + 390.67050646 * k - 0.0016528 * T2 - 0.00000239 * T3
    C1 = (0.1734 - 0.000393 * T) * math.sin(m * dr) + 0.0021 * math.sin(2 * dr * m)
    C1 -= 0.4068 * math.sin(Mpr * dr) - 0.0161 * math.sin(dr * 2 * Mpr)
    C1 -= 0.0004 * math.sin(dr * 3 * Mpr)
    C1 += 0.0104 * math.sin(dr * 2 * F) - 0.0051 * math.sin(dr * (m + Mpr))
    C1 += -0.0074 * math.sin(dr * (m - Mpr)) + 0.0004 * math.sin(dr * (2 * F + m))
    C1 += -0.0004 * math.sin(dr * (2 * F - m)) - 0.0006 * math.sin(dr * (2 * F + Mpr))
    C1 += 0.001 * math.sin(dr * (2 * F - Mpr)) + 0.0005 * math.sin(dr * (2 * Mpr + m))
    if T < -11:
        deltat = 0.001 + 0.000839 * T + 0.0002261 * T2 - 0.00000845 * T3 - 0.000000081 * T * T3
    else:
        deltat = -0.000278 + 0.000265 * T + 0.000262 * T2
    return Jd1 + C1 - deltat


def sun_longitude(jdn: float) -> float:
    T = (jdn - 2451545.0) / 36525.0
    T2 = T * T
    dr = PI / 180.0
    m = 357.5291 + 35999.0503 * T - 0.0001559 * T2 - 0.00000048 * T * T2
    L0 = 280.46645 + 36000.76983 * T + 0.0003032 * T2
    DL = (1.9146 - 0.004817 * T - 0.000014 * T2) * math.sin(dr * m)
    DL += (0.019993 - 0.000101 * T) * math.sin(dr * 2 * m) + 0.00029 * math.sin(dr * 3 * m)
    L = (L0 + DL) * dr
    L = L - PI * 2 * math.floor(L / (PI * 2))
    return L


def get_sun_longitude(day_number: float, time_zone: float = 7.0) -> int:
    return int(math.floor(sun_longitude(day_number - 0.5 - time_zone / 24.0) / PI * 6.0))


def get_new_moon_day(k: int, time_zone: float = 7.0) -> int:
    return int(math.floor(new_moon(k) + 0.5 + time_zone / 24.0))


def get_lunar_month11(yy: int, time_zone: float = 7.0) -> int:
    off = jd_from_date(31, 12, yy) - 2415021
    k = int(math.floor(off / 29.530588853))
    nm = get_new_moon_day(k, time_zone)
    sun_long = get_sun_longitude(nm, time_zone)
    if sun_long >= 9:
        nm = get_new_moon_day(k - 1, time_zone)
    return nm


def get_leap_month_offset(a11: float, time_zone: float = 7.0) -> int:
    k = int(math.floor((a11 - 2415021.07699869) / 29.530588853 + 0.5))
    last = 0
    i = 1
    arc = get_sun_longitude(get_new_moon_day(k + i, time_zone), time_zone)
    while True:
        last = arc
        i += 1
        arc = get_sun_longitude(get_new_moon_day(k + i, time_zone), time_zone)
        if arc == last or i >= 14:
            break
    return i - 1


def solar_to_lunar(dd: int, mm: int, yy: int, time_zone: float = 7.0) -> Tuple[int, int, int, bool]:
    day_number = jd_from_date(dd, mm, yy)
    k = int(math.floor((day_number - 2415021.07699869) / 29.530588853))
    month_start = get_new_moon_day(k + 1, time_zone)
    if month_start > day_number:
        month_start = get_new_moon_day(k, time_zone)
    a11 = get_lunar_month11(yy, time_zone)
    b11 = a11
    if a11 >= month_start:
        lunar_year = yy
        a11 = get_lunar_month11(yy - 1, time_zone)
    else:
        lunar_year = yy + 1
        b11 = get_lunar_month11(yy + 1, time_zone)
    lunar_day = day_number - month_start + 1
    diff = int(math.floor((month_start - a11) / 29))
    lunar_leap = 0
    lunar_month = diff + 11
    if b11 - a11 > 365:
        leap_month_diff = get_leap_month_offset(a11, time_zone)
        if diff >= leap_month_diff:
            lunar_month = diff + 10
            if diff == leap_month_diff:
                lunar_leap = 1
    if lunar_month > 12:
        lunar_month -= 12
    if lunar_month >= 11 and diff < 4:
        lunar_year -= 1
    return lunar_day, lunar_month, lunar_year, bool(lunar_leap)


def get_can_chi(dd: int, mm: int, yy: int) -> Dict[str, Any]:
    """Tính toán Can Chi của Ngày, Tháng, Năm, Giờ, Tiết Khí, Hoàng Đạo."""
    jd = jd_from_date(dd, mm, yy)
    ld, lm, ly, leap = solar_to_lunar(dd, mm, yy)

    # Can Chi Năm
    can_year = (ly + 6) % 10
    chi_year = (ly + 8) % 12
    nam_can_chi = f"{CAN[can_year]} {CHI[chi_year]}"

    # Can Chi Tháng
    can_month = (ly * 12 + lm + 3) % 10
    chi_month = (lm + 1) % 12
    thang_can_chi = f"{CAN[can_month]} {CHI[chi_month]}"

    # Can Chi Ngày
    can_day = (jd + 9) % 10
    chi_day = (jd + 1) % 12
    ngay_can_chi = f"{CAN[can_day]} {CHI[chi_day]}"

    # Tiết khí
    sun_l = sun_longitude(jd - 0.5 - 7.0 / 24.0)
    tiet_idx = int(math.floor(sun_l / (PI * 2) * 24.0)) % 24
    tiet_khi = TIET_KHI[tiet_idx]

    # Giờ Hoàng Đạo
    hoang_dao_hours = HOANG_DAO_DICT.get(chi_day, [])
    hoang_dao_names = [h[1] for h in hoang_dao_hours]

    # Hướng xuất hành
    hy_thanh = HY_THANH.get(can_day, "Chính Nam")
    tai_thanh = TAI_THANH.get(can_day, "Chính Đông")

    # Đánh giá Ngày Hoàng Đạo / Hắc Đạo
    # Dựa trên Chi ngày & tháng
    is_hoang_dao_day = (chi_day in [0, 4, 8, 2, 6, 10])

    # Gợi ý việc nên làm / kiêng cữ thực chiến công trường
    if is_hoang_dao_day:
        khuyen_nghi = "Ngày Hoàng Đạo cát lành: Rất thích hợp khởi công, đổ bê tông móng/sàn, cất nóc, ký hợp đồng kinh tế, giao dịch tài chính."
        viec_nen = "Khởi công, động thổ, đổ mái, ký hợp đồng thầu, xuất hàng."
        viec_kieng = "Tranh chấp, kiện tụng, dồn ép tổ đội quá mức."
    else:
        khuyen_nghi = "Ngày bình hòa / cần cẩn trọng: Nên tập trung kiểm tra chất lượng hiện trường, rà soát hồ sơ thanh quyết toán, nghiệm thu nội bộ."
        viec_nen = "Nghiệm thu nội bộ, bảo dưỡng thiết bị máy móc, đối chiếu công nợ."
        viec_kieng = "Khởi công công trình lớn, động thổ móng sâu trong thời tiết xấu."

    return {
        "solar_day": dd,
        "solar_month": mm,
        "solar_year": yy,
        "lunar_day": ld,
        "lunar_month": lm,
        "lunar_year": ly,
        "is_leap": leap,
        "nam_can_chi": nam_can_chi,
        "thang_can_chi": thang_can_chi,
        "ngay_can_chi": ngay_can_chi,
        "tiet_khi": tiet_khi,
        "hoang_dao_hours": hoang_dao_names,
        "hy_thanh": hy_thanh,
        "tai_thanh": tai_thanh,
        "is_hoang_dao_day": is_hoang_dao_day,
        "khuyen_nghi": khuyen_nghi,
        "viec_nen": viec_nen,
        "viec_kieng": viec_kieng
    }


# =============================================================================
# THUẬT TOÁN NHỊP SINH HỌC (BIORHYTHM) THỰC CHIẾN
# =============================================================================

def calculate_biorhythm(birth_date: datetime.date, target_date: Optional[datetime.date] = None) -> Dict[str, Any]:
    """
    Tính toán 4 chỉ số nhịp sinh học:
    - Thể chất (Physical - 23 ngày)
    - Cảm xúc (Emotional - 28 ngày)
    - Trí tuệ (Intellectual - 33 ngày)
    - Trực giác (Intuitive - 38 ngày)
    """
    if target_date is None:
        target_date = datetime.date.today()

    delta_days = (target_date - birth_date).days

    # Tính phần trăm từ -100% đến +100%
    p_val = math.sin(2.0 * PI * delta_days / 23.0) * 100.0
    e_val = math.sin(2.0 * PI * delta_days / 28.0) * 100.0
    i_val = math.sin(2.0 * PI * delta_days / 33.0) * 100.0
    int_val = math.sin(2.0 * PI * delta_days / 38.0) * 100.0
    overall = (p_val + e_val + i_val) / 3.0

    # Kiểm tra ngày tới hạn (Critical Day: khi chuyển qua giá trị 0)
    p_crit = abs(p_val) < 8.0 or (delta_days % 23 in [0, 11, 12])
    e_crit = abs(e_val) < 8.0 or (delta_days % 28 in [0, 14])
    i_crit = abs(i_val) < 8.0 or (delta_days % 33 in [0, 16, 17])

    # Lời khuyên thực chiến cho Chỉ huy trưởng / Kỹ sư
    advices = []
    if p_val > 50:
        advices.append("💪 Thể chất sung mãn (Đỉnh phong độ): Rất thích hợp đi hiện trường, leo giàn giáo kiểm tra kết cấu, chỉ đạo các ca đổ bê tông đêm kéo dài.")
    elif p_val < -50:
        advices.append("⚠️ Thể chất ở pha nạp năng lượng: Tránh làm việc quá sức dưới nắng gắt hoặc thức trắng đêm, nên phân công kỹ thuật viên phụ trách bớt.")
    elif p_crit:
        advices.append("🚨 Ngày tới hạn Thể chất (Critical): Phản xạ thể lực có thể chậm, đặc biệt chú ý an toàn lao động khi di chuyển mép sàn, giàn giáo!")

    if e_val > 50:
        advices.append("😊 Cảm xúc thăng hoa: Thời điểm vàng để đàm phán thương thảo hợp đồng, giao lưu gắn kết tổ đội, giải tỏa căng thẳng với TVGS.")
    elif e_val < -50:
        advices.append("🧘 Cảm xúc nhạy cảm: Dễ nảy sinh bực bội khi hiện trường chậm việc; hãy giữ bình tĩnh trong cuộc họp giao ban 16h30, lắng nghe nhiều hơn.")
    elif e_crit:
        advices.append("🚨 Ngày tới hạn Cảm xúc (Critical): Dễ bị kích động tâm lý; tuyệt đối tránh tranh cãi gay gắt hoặc đưa ra quyết định sa thải/phạt nóng.")

    if i_val > 50:
        advices.append("🧠 Trí tuệ sắc bén: Thời điểm lý tưởng để bóc tách khối lượng phức tạp, rà soát kẽ hở hợp đồng FIDIC, lập hồ sơ Claim thanh quyết toán.")
    elif i_val < -50:
        advices.append("☕ Trí tuệ cần nghỉ ngơi: Tránh đọc bản vẽ quá tải vào ban đêm; nên kiểm tra chéo số liệu dự toán ít nhất 2 lần trước khi gửi CĐT.")
    elif i_crit:
        advices.append("🚨 Ngày tới hạn Trí tuệ (Critical): Khả năng tập trung giảm nhẹ; cần rà soát kỹ từng con số trong biên bản nghiệm thu trước khi ký.")

    return {
        "birth_date": birth_date.strftime("%d/%m/%Y"),
        "target_date": target_date.strftime("%d/%m/%Y"),
        "days_lived": delta_days,
        "physical": round(p_val, 1),
        "emotional": round(e_val, 1),
        "intellectual": round(i_val, 1),
        "intuitive": round(int_val, 1),
        "overall": round(overall, 1),
        "physical_critical": p_crit,
        "emotional_critical": e_crit,
        "intellectual_critical": i_crit,
        "advices": advices
    }

