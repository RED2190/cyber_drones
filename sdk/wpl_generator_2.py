# вход -- json с тремя точками
# points: список словарей из json:
#     { //точка start - дронопорт
#     "lat": float,
#     "lon": float,
#     "alt_m": float,
#     },
#
#     { //точка 2 - левый нижний угол прямоугольника
#     "lat": float,
#     "lon": float,
#     "alt_m": float,
#     },
#     { //точка 3 - правый верхний угол прямоугольника
#     "lat": float,
#     "lon": float,
#     "alt_m": float,
#     }

import json
import math

WPL_HEADER = "QGC WPL 110"
DEFAULT_FRAME = 3
DEFAULT_COMMAND = 16
DEFAULT_AUTOCONTINUE = 1

DEFAULT_SEGMENTS_LINE = 5  # сегменты на прямой (1->2 и 3->1)
DEFAULT_RECT_SEGMENTS_X = 4

DEFAULT_RECT_SEGMENTS_Y = 5

# дефолты параметров команд
DEFAULT_PARAM1 = 0.0  # hold time
DEFAULT_PARAM2 = 0.0  # acceptance radius
DEFAULT_PARAM3 = 0.0  # pass through
DEFAULT_PARAM4 = 0.0  # yaw


def get_required(point, field, index):
    if field not in point:
        raise ValueError(f"Point #{index} missing required field '{field}'")
    return point[field]


def to_float(value, field_name):
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValueError(f"Field '{field_name}' must be a number, got: {value!r}")


def validate_lat_lon(lat, lon):
    if lat < -90 or lat > 90:
        raise ValueError(f"Latitude out of range [-90..90]: {lat}")
    if lon < -180 or lon > 180:
        raise ValueError(f"Longitude out of range [-180..180]: {lon}")


def _earth_radius_m() -> float:
    #для локальной аппроксимации
    return 6371000.0


def _deg_to_rad(d: float) -> float:
    return d * math.pi / 180.0


def _rad_to_deg(r: float) -> float:
    return r * 180.0 / math.pi


def _ll_to_local_xy_m(lat, lon, lat0, lon0):
    """
    Преобразование lat/lon -> локальные x/y в метрах относительно (lat0, lon0)
    x: восток (E), y: север (N).
    """
    r = _earth_radius_m()
    lat_r = _deg_to_rad(lat)
    lon_r = _deg_to_rad(lon)
    lat0_r = _deg_to_rad(lat0)
    lon0_r = _deg_to_rad(lon0)

    dlat = lat_r - lat0_r
    dlon = lon_r - lon0_r

    x = dlon * math.cos(lat0_r) * r
    y = dlat * r
    return x, y


def _local_xy_to_ll(x_m, y_m, lat0, lon0):
    """Обратное преобразование локальных метров в lat/lon."""
    r = _earth_radius_m()
    lat0_r = _deg_to_rad(lat0)
    lon0_r = _deg_to_rad(lon0)

    lat = lat0_r + (y_m / r)
    lon = lon0_r + (x_m / (math.cos(lat0_r) * r))

    return _rad_to_deg(lat), _rad_to_deg(lon)


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _point(lat, lon, alt_m):
    return {
        "lat": float(lat),
        "lon": float(lon),
        "alt_m": float(alt_m),
        "param1": DEFAULT_PARAM1,
        "param2": DEFAULT_PARAM2,
        "param3": DEFAULT_PARAM3,
        "param4": DEFAULT_PARAM4,
    }


def _interpolate_line(p0, p1, segments: int):
    """
    Возвращает точки на прямой включая оба конца.
    segments=5 => 6 точек.
    """
    if segments <= 0:
        raise ValueError("Segments must be > 0")

    out = []
    for i in range(segments + 1):
        t = i / segments
        out.append(
            _point(
                _lerp(p0["lat"], p1["lat"], t),
                _lerp(p0["lon"], p1["lon"], t),
                _lerp(p0["alt_m"], p1["alt_m"], t),
            )
        )
    return out


def expand_three_points_to_snake_path(
    points,
    line_segments: int = DEFAULT_SEGMENTS_LINE,
    rect_segments_x: int = DEFAULT_RECT_SEGMENTS_X,
    rect_segments_y: int = DEFAULT_RECT_SEGMENTS_Y,
):
    """
    Вход: 3 точки (start, rect_bottom_left, rect_top_right) со значениями lat/lon/alt_m.
    Выход: путь:
      1) прямая 1->2 (line_segments сегментов)
      2) змейка по прямоугольнику от 2 до 3:
      3) прямая 3->1 (line_segments сегментов)
    """
    if not isinstance(points, list):
        raise ValueError(f"JSON root must be a list of points, got: {type(points).__name__}")
    if len(points) != 3:
        raise ValueError(f"Expected exactly 3 points (start, p2, p3), got: {len(points)}")

    if line_segments <= 0:
        raise ValueError("line_segments must be > 0")
    if rect_segments_x <= 0:
        raise ValueError("rect_segments_x must be > 0")
    if rect_segments_y <= 0:
        raise ValueError("rect_segments_y must be > 0")

    p1_raw, p2_raw, p3_raw = points
    for idx, p in enumerate((p1_raw, p2_raw, p3_raw)):
        if not isinstance(p, dict):
            raise ValueError(f"Point #{idx} must be a dict, got: {type(p).__name__}")

    def read_point(p, idx):
        lat = to_float(get_required(p, "lat", idx), "lat")
        lon = to_float(get_required(p, "lon", idx), "lon")
        alt = to_float(get_required(p, "alt_m", idx), "alt_m")
        validate_lat_lon(lat, lon)
        if alt < 0:
            raise ValueError(f"Altitude must be >=0, got point #{idx}: {alt}")
        return {"lat": lat, "lon": lon, "alt_m": alt}

    p1 = read_point(p1_raw, 0)
    p2 = read_point(p2_raw, 1)  # левый нижний
    p3 = read_point(p3_raw, 2)  # правый верхний

    x3, y3 = _ll_to_local_xy_m(p3["lat"], p3["lon"], p2["lat"], p2["lon"])
    if x3 <= 0 or y3 <= 0:
        raise ValueError(
            "Rectangle corners must satisfy: point #2 is bottom-left, point #3 is top-right "
            "(p3 must be east and north of p2)."
        )

    # 1) Прямая p1->p2
    leg_12 = _interpolate_line(p1, p2, segments=line_segments)

    # 2) Змейка внутри прямоугольника p2->p3
    # В локальной СК: p2=(0,0), p3=(W,H)
    W = x3  # ширина прямоугольника в метрах
    H = y3  # высота прямоугольника в метрах
    t_step = W / rect_segments_x
    k_step = H / rect_segments_y

    snake_xy = []
    cols = rect_segments_x + 1
    rows = rect_segments_y + 1

    reached_end = False

    for col in range(cols):
        x = col * t_step
        going_up = (col % 2 == 0)

        if going_up:
            y_values = [j * k_step for j in range(rows)]  # 0..H
        else:
            y_values = [j * k_step for j in reversed(range(rows))]  # H..0

        for y in y_values:
            if snake_xy and abs(snake_xy[-1][0] - x) < 1e-9 and abs(snake_xy[-1][1] - y) < 1e-9:
                continue
            snake_xy.append((x, y))
            if abs(x - W) < 1e-6 and abs(y - H) < 1e-6:
                reached_end = True
                break

        if reached_end:
            break

    if not reached_end:
        raise ValueError("Snake path did not reach the top-right corner (p3). Check rect_segments_x/y and points order.")

    snake_xy[0] = (0.0, 0.0)
    snake_xy[-1] = (W, H)

    # snake_xy -> snake (lat/lon/alt_m) + интерполяция высоты
    snake_total_points = len(snake_xy)
    if snake_total_points < 2:
        raise ValueError("Snake path is too short")

    snake = []
    for n, (xx, yy) in enumerate(snake_xy):
        progress = n / (snake_total_points - 1)
        alt = _lerp(p2["alt_m"], p3["alt_m"], progress)

        lat, lon = _local_xy_to_ll(xx, yy, p2["lat"], p2["lon"])
        validate_lat_lon(lat, lon)
        snake.append(_point(lat, lon, alt))

    # Зафиксируем начало/конец точно по входу (микропогрешности преобразования)
    snake[0] = _point(p2["lat"], p2["lon"], p2["alt_m"])
    snake[-1] = _point(p3["lat"], p3["lon"], p3["alt_m"])

    # 3) Прямая p3->p1
    leg_31 = _interpolate_line(p3, p1, segments=line_segments)

    path = leg_12 + snake[1:] + leg_31[1:]
    return path


def points_to_wpl(points, frame=DEFAULT_FRAME):
    if not points:
        raise ValueError("Points array is empty")

    lines = [WPL_HEADER]

    for i, p in enumerate(points):
        if not isinstance(p, dict):
            raise ValueError(f"Point #{i} must be a dict, got: {type(p).__name__}")

        lat = to_float(get_required(p, "lat", i), "lat")
        lon = to_float(get_required(p, "lon", i), "lon")
        alt = to_float(get_required(p, "alt_m", i), "alt_m")
        validate_lat_lon(lat, lon)

        if alt < 0:
            raise ValueError(f"Altitude must be >=0, got point #{i}: {alt}")

        param1 = to_float(p.get("param1", DEFAULT_PARAM1), "param1")
        param2 = to_float(p.get("param2", DEFAULT_PARAM2), "param2")
        param3 = to_float(p.get("param3", DEFAULT_PARAM3), "param3")
        param4 = to_float(p.get("param4", DEFAULT_PARAM4), "param4")

        current = 1 if i == 0 else 0

        row = "\t".join(
            [
                str(i),
                str(current),
                str(frame),
                str(DEFAULT_COMMAND),
                str(param1),
                str(param2),
                str(param3),
                str(param4),
                str(lat),
                str(lon),
                str(alt),
                str(DEFAULT_AUTOCONTINUE),
            ]
        )
        lines.append(row)

    return "\n".join(lines) + "\n"


def json_to_wpl(
    input_path,
    output_path,
    frame=DEFAULT_FRAME,
    line_segments=DEFAULT_SEGMENTS_LINE,
    rect_segments_x=DEFAULT_RECT_SEGMENTS_X,
    rect_segments_y=DEFAULT_RECT_SEGMENTS_Y,
):
    try:
        with open(input_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"Input file not found: {input_path}")
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in {input_path}: {e}")

    expanded_points = expand_three_points_to_snake_path(
        data,
        line_segments=line_segments,
        rect_segments_x=rect_segments_x,
        rect_segments_y=rect_segments_y,
    )
    wpl_text = points_to_wpl(expanded_points, frame=frame)

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(wpl_text)
    except OSError as e:
        raise OSError(f"Cannot write to output file {output_path}: {e}")
