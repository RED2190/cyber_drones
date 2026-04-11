import json

WPL_HEADER = "QGC WPL 110"
DEFAULT_FRAME = 3 # относительная высота, отсчет от точки взлета
DEFAULT_COMMAND = 16 # номер команды из MavLink (лети в точку)
DEFAULT_AUTOCONTINUE = 1 # автоматически продолжать при достижении точки
DEFAULT_SEGMENTS = 5 # количество сегментов для плавного пролета между точками
DEFAULT_PARAM1 = 0.0
DEFAULT_PARAM2 = 0.0
DEFAULT_PARAM3 = 0.0
DEFAULT_PARAM4 = 0.0

def get_required(point, field, index):
    if field not in point:
        raise ValueError(f"Point #{index} missing required field '{field}'")
    return point[field]

def to_float(value, field_name):
    try:
        return float(value)
    except (TypeError, ValueError) as e:
        raise ValueError(f"Field '{field_name}' must be a number, got: {value!r}")

def validate_lat_lon(lat,lon):
    if lat<-90 or lat>90:
        raise ValueError(f"Latitude out of range [-90..90]: {lat}")
    if lon<-180 or lon>180:
        raise ValueError(f"Longitude out of range [-180..180]: {lon}")



# вход -- json с двумя точками
# points: список словарей из json:
#     { //точка start
#     "lat": float,
#     "lon": float,
#     "alt": float,
#     },

#     { //точка end
#     "lat": float,
#     "lon": float,
#     "alt": float,
#     }

def expand_two_points_to_path(points, segments=DEFAULT_SEGMENTS):
    if not isinstance(points, list):
        raise ValueError(f"JSON root must be a list of points, got: {type(points).__name__}")

    if len(points) != 2:
        raise ValueError(f"Expected exactly 2 points (start, end), got: {len(points)}")

    if segments <= 0:
        raise ValueError("Segments must be > 0")

    start = points[0]
    end = points[1]

    if not isinstance(start, dict) or not isinstance(end, dict):
        raise ValueError("Start and end points must be dict objects")
    # start
    lat0 = to_float(get_required(start, "lat", 0), "lat")
    lon0 = to_float(get_required(start, "lon", 0), "lon")
    alt0 = to_float(get_required(start, "alt", 0), "alt")
    validate_lat_lon(lat0, lon0)
    if alt0 < 0:
        raise ValueError(f"Altitude must be >=0, got start alt: {alt0}")

    s_param1 = to_float(start.get("param1", DEFAULT_PARAM1), "param1")
    s_param2 = to_float(start.get("param2", DEFAULT_PARAM2), "param2")
    s_param3 = to_float(start.get("param3", DEFAULT_PARAM3), "param3")

    # end
    lat1 = to_float(get_required(end, "lat", 1), "lat")
    lon1 = to_float(get_required(end, "lon", 1), "lon")
    alt1 = to_float(get_required(end, "alt", 1), "alt")
    validate_lat_lon(lat1, lon1)
    if alt1 < 0:
        raise ValueError(f"Altitude must be >=0, got end alt: {alt1}")
    if lat0 == lat1 and lon0 == lon1:
        raise ValueError("Start and end points must be different")


    e_param1 = to_float(end.get("param1", DEFAULT_PARAM1), "param1")
    e_param2 = to_float(end.get("param2", DEFAULT_PARAM2), "param2")
    e_param3 = to_float(end.get("param3", DEFAULT_PARAM3), "param3")

    path = []
    for i in range(segments + 1):
        t = i / segments

        lat = lat0 + t * (lat1 - lat0)
        lon = lon0 + t * (lon1 - lon0)
        alt = alt0 + t * (alt1 - alt0)

        if i == 0:
            param1, param2, param3 = s_param1, s_param2, s_param3
        elif i == segments:
            param1, param2, param3 = e_param1, e_param2, e_param3
        else:
            param1, param2, param3 = 0.0, s_param2, 0.0

        path.append(
            {
                "lat": lat,
                "lon": lon,
                "alt": alt,
                "param1": param1,
                "param2": param2,
                "param3": param3,
                "param4": DEFAULT_PARAM4,
            }
        )
        
    back_path = list(reversed(path[:-1]))
    cycle_path = path + back_path
    return cycle_path


def points_to_wpl(points, frame = DEFAULT_FRAME):
    if not points:
        raise ValueError("Points array is empty")

    lines = [WPL_HEADER]

    for i, p in enumerate(points):

        if not isinstance(p, dict):
            raise ValueError(f"Point #{i} must be a dict, got: {type(p).__name__}")

        lat = to_float(get_required(p, "lat", i), "lat")
        lon = to_float(get_required(p, "lon", i), "lon")
        alt = to_float(get_required(p, "alt", i), "alt")

        validate_lat_lon(lat,lon)

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

def json_to_wpl(input_path, output_path, frame=DEFAULT_FRAME, segments=DEFAULT_SEGMENTS):
    try:
        with open(input_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"Input file not found: {input_path}")
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in {input_path}: {e}")

    expanded_points = expand_two_points_to_path(data, segments=segments)
    wpl_text = points_to_wpl(expanded_points, frame=frame)

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(wpl_text)
    except OSError as e:
        raise OSError(f"Cannot write to output file {output_path}: {e}")
