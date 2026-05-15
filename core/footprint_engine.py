# -*- coding: utf-8 -*-
"""
planX — Yerleşim Planı Araç Seti
Footprint Engine — yapı nizamı ve emsal odaklı footprint üretim motoru
"""

import math

from qgis.core import QgsGeometry, QgsPointXY

from .geometry_engine import (
    get_polygon_edges,
    negative_buffer_per_edge,
    oriented_minimum_bounding_box,
    scale_geometry_to_area,
)

NIZAM_DETACHED = "A"
NIZAM_BLOCK = "BL"
NIZAM_ATTACHED = "B"

BLOCK_OPEN_SIDE_AUTO = "auto"
BLOCK_OPEN_SIDE_FIRST = "first"
BLOCK_OPEN_SIDE_LAST = "last"

_FAR_ASPECT_OPTIONS = (1.2, 1.5, 1.8, 2.2)


def parse_edge_indices(raw_value):
    """Cephe alanlarındaki kenar indekslerini listeye çevirir."""
    if raw_value in (None, ""):
        return []
    return [int(x) for x in str(raw_value).split(",") if x.strip().isdigit()]


def normalize_nizam_code(raw_value, default_code=NIZAM_DETACHED):
    """Ham öznitelik değerini A / B / BL kodlarından birine normalize eder."""
    text = str(raw_value or "").strip().upper()
    if text in (NIZAM_DETACHED, NIZAM_ATTACHED, NIZAM_BLOCK):
        return text
    return default_code


def feature_facade_indices(feature, field_index_map):
    """Ön/yan/arka cephe kenarlarını feature içinden okur."""
    def _read(name):
        if name not in field_index_map:
            return []
        return parse_edge_indices(feature[field_index_map[name]])

    return {
        "front": _read("facade_front"),
        "side": _read("facade_side"),
        "back": _read("facade_back"),
    }


def _edge_length(edge):
    p1, p2 = edge
    return p1.distance(p2)


def choose_block_open_side(side_indices, edges, mode=BLOCK_OPEN_SIDE_AUTO):
    """
    Blok nizamda yan bahçe bırakılacak kenarı seçer.

    Auto modunda daha uzun yan kenarı açık bırakmak, kütlenin
    daha dengeli yerleşmesini sağlar.
    """
    if not side_indices:
        return None

    ordered = sorted(side_indices)
    if mode == BLOCK_OPEN_SIDE_FIRST:
        return ordered[0]
    if mode == BLOCK_OPEN_SIDE_LAST:
        return ordered[-1]

    return max(ordered, key=lambda idx: _edge_length(edges[idx]) if idx < len(edges) else 0.0)


def build_nizam_configuration(
    parcel_geom,
    facade_indices,
    setback_front,
    setback_side,
    setback_back,
    nizam_code,
    block_open_side_mode=BLOCK_OPEN_SIDE_AUTO,
):
    """
    Yapı nizamına göre kenar setback listesini ve TAKS küçültmede
    ayarlanabilecek kenarları döndürür.
    """
    edges = get_polygon_edges(parcel_geom)
    edge_count = len(edges)
    front_indices = list(facade_indices.get("front", []))
    side_indices = list(facade_indices.get("side", []))
    back_indices = list(facade_indices.get("back", []))

    edge_setbacks = [0.0] * edge_count
    adjustable_indices = set()
    attached_indices = set()
    block_open_side = None

    if nizam_code == NIZAM_ATTACHED:
        for idx in front_indices:
            if idx < edge_count:
                edge_setbacks[idx] = setback_front
                adjustable_indices.add(idx)
        for idx in back_indices:
            if idx < edge_count:
                edge_setbacks[idx] = setback_back
                adjustable_indices.add(idx)
        for idx in side_indices:
            if idx < edge_count:
                edge_setbacks[idx] = 0.0
                attached_indices.add(idx)

    elif nizam_code == NIZAM_BLOCK:
        block_open_side = choose_block_open_side(
            side_indices, edges, block_open_side_mode
        )
        for idx in front_indices:
            if idx < edge_count:
                edge_setbacks[idx] = setback_front
                adjustable_indices.add(idx)
        for idx in back_indices:
            if idx < edge_count:
                edge_setbacks[idx] = setback_back
                adjustable_indices.add(idx)
        for idx in side_indices:
            if idx >= edge_count:
                continue
            if idx == block_open_side:
                edge_setbacks[idx] = setback_side
                adjustable_indices.add(idx)
            else:
                edge_setbacks[idx] = 0.0
                attached_indices.add(idx)

    else:
        for idx in front_indices:
            if idx < edge_count:
                edge_setbacks[idx] = setback_front
                adjustable_indices.add(idx)
        for idx in side_indices:
            if idx < edge_count:
                edge_setbacks[idx] = setback_side
                adjustable_indices.add(idx)
        for idx in back_indices:
            if idx < edge_count:
                edge_setbacks[idx] = setback_back
                adjustable_indices.add(idx)

    # FacadeDetector kenarları sınıflandırmadıysa konservatif fallback:
    # ayrıkta yan bahçe, bitişikte 0, blokta ise seçilen açık yanda yan bahçe.
    for idx in range(edge_count):
        if idx in front_indices or idx in side_indices or idx in back_indices:
            continue
        if nizam_code == NIZAM_ATTACHED:
            edge_setbacks[idx] = 0.0
            attached_indices.add(idx)
        elif nizam_code == NIZAM_BLOCK:
            if block_open_side is None:
                block_open_side = idx
            if idx == block_open_side:
                edge_setbacks[idx] = setback_side
                adjustable_indices.add(idx)
            else:
                edge_setbacks[idx] = 0.0
                attached_indices.add(idx)
        else:
            edge_setbacks[idx] = setback_side
            adjustable_indices.add(idx)

    return {
        "edge_setbacks": edge_setbacks,
        "adjustable_indices": sorted(adjustable_indices),
        "attached_indices": sorted(attached_indices),
        "block_open_side": block_open_side,
    }


def fit_footprint_to_target_area(parcel_geom, base_edge_setbacks, target_area, adjustable_indices):
    """
    TAKS alanına inmek için yalnızca ayarlanabilir kenar setback'lerini
    artırarak footprint küçültür.
    """
    buildable = negative_buffer_per_edge(parcel_geom, base_edge_setbacks)
    if buildable.isEmpty() or target_area <= 0:
        return buildable

    if buildable.area() <= target_area:
        return buildable

    if not adjustable_indices:
        return scale_geometry_to_area(buildable, target_area)

    def _geom_for_delta(delta):
        setbacks = list(base_edge_setbacks)
        for idx in adjustable_indices:
            setbacks[idx] += delta
        return negative_buffer_per_edge(parcel_geom, setbacks)

    lo = 0.0
    hi = 1.0
    best_under = None
    best_over = buildable

    while hi <= 1024.0:
        geom = _geom_for_delta(hi)
        if geom.isEmpty():
            break
        if geom.area() <= target_area:
            best_under = geom
            break
        best_over = geom
        hi *= 2.0

    for _ in range(28):
        mid = (lo + hi) / 2.0
        geom = _geom_for_delta(mid)
        if geom.isEmpty():
            hi = mid
            continue

        area = geom.area()
        if area > target_area:
            lo = mid
            best_over = geom
        else:
            hi = mid
            best_under = geom

    if best_under and not best_under.isEmpty():
        return best_under
    if best_over and not best_over.isEmpty():
        return scale_geometry_to_area(best_over, target_area)
    return QgsGeometry()


def compute_floor_count_from_height(height_value, average_floor_height):
    """Yençok / Hmax değerinden kat adedi türetir."""
    try:
        height = float(height_value or 0)
    except (TypeError, ValueError):
        return 1

    if height <= 0 or average_floor_height <= 0:
        return 1
    return max(1, int(round(height / average_floor_height)))


def compute_far_side_yard(floor_count):
    """Emsal çözümünde bina yan bahçesi hesabı."""
    if floor_count <= 4:
        return 3.0
    return 3.0 + (floor_count - 4) * 0.5


def _local_rect_to_world(center_pt, angle_deg, local_cx, local_cy, rect_w, rect_h):
    angle_rad = math.radians(angle_deg)
    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)
    hw = rect_w / 2.0
    hh = rect_h / 2.0
    coords = [
        (local_cx - hw, local_cy - hh),
        (local_cx + hw, local_cy - hh),
        (local_cx + hw, local_cy + hh),
        (local_cx - hw, local_cy + hh),
        (local_cx - hw, local_cy - hh),
    ]

    points = []
    for x, y in coords:
        wx = center_pt.x() + x * cos_a - y * sin_a
        wy = center_pt.y() + x * sin_a + y * cos_a
        points.append(QgsPointXY(wx, wy))
    return QgsGeometry.fromPolygonXY([points])


def _sorted_candidate_counts(target_total_area, min_building_area, max_building_area):
    if target_total_area <= 0:
        return [1]

    min_count = max(1, int(math.ceil(target_total_area / max(max_building_area, 1e-6))))
    max_count = max(1, int(math.floor(target_total_area / max(min_building_area, 1e-6))))
    if max_count < min_count:
        return [1]

    ideal_area = (min_building_area + max_building_area) / 2.0
    if ideal_area <= 0:
        ideal_area = max_building_area or target_total_area
    ideal_count = max(1, int(round(target_total_area / ideal_area)))

    counts = list(range(min_count, max_count + 1))
    return sorted(counts, key=lambda n: (abs(n - ideal_count), n))


def generate_far_footprints(
    block_geom,
    target_total_area,
    min_building_area,
    max_building_area,
    fixed_setback,
    spacing_distance,
):
    """
    Emsal adası içinde parametrik footprint üretir.

    Çıktı:
        {
            'buildable_geom': QgsGeometry,
            'footprints': list[QgsGeometry],
            'layout_type': str,
            'building_count': int,
            'per_building_area': float
        }
    """
    buildable = block_geom.buffer(-fixed_setback, 8)
    if buildable.isEmpty():
        return {
            "buildable_geom": QgsGeometry(),
            "footprints": [],
            "layout_type": "bos",
            "building_count": 0,
            "per_building_area": 0.0,
        }

    buildable_area = buildable.area()
    target_total_area = max(0.0, min(target_total_area, buildable_area))
    if target_total_area <= 0:
        return {
            "buildable_geom": buildable,
            "footprints": [],
            "layout_type": "hedef_yok",
            "building_count": 0,
            "per_building_area": 0.0,
        }

    obb = oriented_minimum_bounding_box(buildable)
    if not obb:
        fallback = scale_geometry_to_area(buildable, target_total_area)
        return {
            "buildable_geom": buildable,
            "footprints": [fallback] if not fallback.isEmpty() else [],
            "layout_type": "fallback",
            "building_count": 1 if not fallback.isEmpty() else 0,
            "per_building_area": fallback.area() if not fallback.isEmpty() else 0.0,
        }

    width = obb["width"]
    height = obb["height"]
    angle = obb["angle"]
    center = obb["center"]

    if width < height:
        width, height = height, width
        angle += 90.0

    tol_geom = buildable.buffer(0.01, 2)

    for building_count in _sorted_candidate_counts(
        target_total_area, min_building_area, max_building_area
    ):
        per_building_area = target_total_area / max(building_count, 1)
        if building_count > 1 and (
            per_building_area < min_building_area or per_building_area > max_building_area
        ):
            continue

        for aspect in _FAR_ASPECT_OPTIONS:
            rect_w = math.sqrt(per_building_area * aspect)
            rect_h = per_building_area / max(rect_w, 1e-6)

            for rw, rh in ((rect_w, rect_h), (rect_h, rect_w)):
                for cols in range(1, building_count + 1):
                    rows = int(math.ceil(building_count / float(cols)))
                    total_w = cols * rw + (cols - 1) * spacing_distance
                    total_h = rows * rh + (rows - 1) * spacing_distance
                    if total_w > width + 1e-6 or total_h > height + 1e-6:
                        continue

                    origin_x = -total_w / 2.0 + rw / 2.0
                    origin_y = -total_h / 2.0 + rh / 2.0
                    footprints = []
                    fit_all = True

                    for idx in range(building_count):
                        col = idx % cols
                        row = idx // cols
                        local_cx = origin_x + col * (rw + spacing_distance)
                        local_cy = origin_y + row * (rh + spacing_distance)
                        rect = _local_rect_to_world(center, angle, local_cx, local_cy, rw, rh)
                        if rect.isEmpty() or not tol_geom.contains(rect):
                            fit_all = False
                            break
                        footprints.append(rect)

                    if fit_all and footprints:
                        return {
                            "buildable_geom": buildable,
                            "footprints": footprints,
                            "layout_type": "grid",
                            "building_count": building_count,
                            "per_building_area": per_building_area,
                        }

    fallback = scale_geometry_to_area(buildable, target_total_area)
    return {
        "buildable_geom": buildable,
        "footprints": [fallback] if not fallback.isEmpty() else [],
        "layout_type": "fallback",
        "building_count": 1 if not fallback.isEmpty() else 0,
        "per_building_area": fallback.area() if not fallback.isEmpty() else 0.0,
    }


def guess_ada_id_field(field_names):
    """Ada kimliğini taşıyan en olası alan adını döndürür."""
    for candidate in ("ada_id", "source_ada_id", "planx_ada_id", "block_id"):
        if candidate in field_names:
            return candidate
    return None


def guess_parcel_id_field(field_names):
    """Parsel kimliğini taşıyan en olası alan adını döndürür."""
    for candidate in ("parcel_id", "parcel_uid", "planx_parcel_id"):
        if candidate in field_names:
            return candidate
    return None


def combine_geometries(geometries):
    """Geometri listesini tek geometriye birleştirir."""
    result = QgsGeometry()
    for geom in geometries:
        if geom is None or geom.isEmpty():
            continue
        if result.isEmpty():
            result = QgsGeometry(geom)
        else:
            result = result.combine(geom)
    return result


def edge_geometries(geom):
    """Poligon kenarlarını çizgi geometrileri olarak döndürür."""
    return [QgsGeometry.fromPolylineXY([p1, p2]) for p1, p2 in get_polygon_edges(geom)]


def attachable_side_indices(facade_indices, edge_count):
    """Bina gruplamasında yan komşuluğa aday olabilecek kenar indeksleri."""
    front = set(facade_indices.get("front", []))
    back = set(facade_indices.get("back", []))
    side = set(facade_indices.get("side", []))
    if side:
        return side
    return set(range(edge_count)) - front - back


def make_parcel_record(feature, field_index_map, ada_id_field=None, parcel_id_field=None):
    """Ada bazlı nizam algoritmaları için parsel özet kaydı üretir."""
    geom = feature.geometry()
    edges = get_polygon_edges(geom)
    facade = feature_facade_indices(feature, field_index_map)

    ada_value = feature[field_index_map[ada_id_field]] if ada_id_field and ada_id_field in field_index_map else feature.id()
    parcel_value = feature[field_index_map[parcel_id_field]] if parcel_id_field and parcel_id_field in field_index_map else feature.id()

    return {
        "feature": feature,
        "feature_id": feature.id(),
        "ada_id": ada_value,
        "parcel_id": parcel_value,
        "geometry": geom,
        "edges": edges,
        "edge_geometries": edge_geometries(geom),
        "facade_indices": facade,
        "attachable_side_indices": attachable_side_indices(facade, len(edges)),
        "centroid": geom.centroid().asPoint(),
        "bbox": geom.boundingBox(),
        "area": geom.area(),
    }


def _best_matching_edge_index(shared_geom, record, allowed_indices=None, tolerance=0.10):
    best_idx = None
    best_len = 0.0
    allowed = allowed_indices if allowed_indices is not None else set(range(len(record["edge_geometries"])))

    for idx, edge_geom in enumerate(record["edge_geometries"]):
        if idx not in allowed:
            continue
        overlap = edge_geom.intersection(shared_geom)
        if overlap.isEmpty():
            continue
        overlap_len = overlap.length()
        if overlap_len > best_len:
            best_len = overlap_len
            best_idx = idx

    if best_len <= tolerance:
        return None
    return best_idx


def build_side_adjacency(parcel_records, tolerance=0.10):
    """
    Aynı adadaki parseller arasında yan-yana komşuluk grafiği kurar.

    Sadece ortak sınırı yan kenar olarak okunan parseller bağlanır.
    """
    adjacency = {record["feature_id"]: {} for record in parcel_records}
    records = list(parcel_records)

    for i in range(len(records)):
        left = records[i]
        for j in range(i + 1, len(records)):
            right = records[j]
            if left["ada_id"] != right["ada_id"]:
                continue
            if not left["bbox"].intersects(right["bbox"]):
                continue

            shared = left["geometry"].intersection(right["geometry"])
            if shared.isEmpty() or shared.length() <= tolerance:
                continue

            left_idx = _best_matching_edge_index(shared, left, left["attachable_side_indices"], tolerance)
            right_idx = _best_matching_edge_index(shared, right, right["attachable_side_indices"], tolerance)
            if left_idx is None or right_idx is None:
                continue

            shared_len = shared.length()
            adjacency[left["feature_id"]][right["feature_id"]] = {
                "self_edge": left_idx,
                "other_edge": right_idx,
                "shared_length": shared_len,
            }
            adjacency[right["feature_id"]][left["feature_id"]] = {
                "self_edge": right_idx,
                "other_edge": left_idx,
                "shared_length": shared_len,
            }

    return adjacency


def connected_components_from_adjacency(adjacency):
    """Komşuluk grafiğinden bağlı bileşen listesi üretir."""
    components = []
    visited = set()

    for node in adjacency.keys():
        if node in visited:
            continue
        stack = [node]
        component = []
        visited.add(node)
        while stack:
            current = stack.pop()
            component.append(current)
            for neighbor in adjacency[current].keys():
                if neighbor in visited:
                    continue
                visited.add(neighbor)
                stack.append(neighbor)
        components.append(component)

    return components


def order_component_as_chain(component_ids, record_map, adjacency):
    """
    Bağlı bileşeni uçtan uca sıralar.

    Lineer zincir değilse dominant eksen boyunca centroid sıralamasına düşer.
    """
    if len(component_ids) <= 1:
        return list(component_ids)

    degrees = {
        node_id: len([nbr for nbr in adjacency[node_id].keys() if nbr in component_ids])
        for node_id in component_ids
    }
    endpoints = [node_id for node_id, degree in degrees.items() if degree <= 1]

    if len(endpoints) >= 1 and all(degree <= 2 for degree in degrees.values()):
        start = endpoints[0]
        if len(endpoints) > 1:
            start = min(
                endpoints,
                key=lambda fid: (record_map[fid]["centroid"].x(), record_map[fid]["centroid"].y()),
            )

        ordered = []
        previous = None
        current = start
        remaining = set(component_ids)

        while current in remaining:
            ordered.append(current)
            remaining.remove(current)
            neighbors = [nbr for nbr in adjacency[current].keys() if nbr in remaining and nbr != previous]
            if not neighbors:
                break
            if len(neighbors) == 1:
                next_node = neighbors[0]
            else:
                next_node = min(
                    neighbors,
                    key=lambda fid: (
                        record_map[fid]["centroid"].x(),
                        record_map[fid]["centroid"].y(),
                    ),
                )
            previous, current = current, next_node

        if not remaining:
            return ordered

    union_geom = combine_geometries([record_map[fid]["geometry"] for fid in component_ids])
    obb = oriented_minimum_bounding_box(union_geom)
    angle = obb["angle"] if obb else 0.0
    axis = math.radians(angle)
    dx = math.cos(axis)
    dy = math.sin(axis)

    return sorted(
        component_ids,
        key=lambda fid: (
            record_map[fid]["centroid"].x() * dx + record_map[fid]["centroid"].y() * dy,
            record_map[fid]["centroid"].x(),
            record_map[fid]["centroid"].y(),
        ),
    )


def partition_block_chain(ordered_ids):
    """
    Blok nizam zincirini ikili / üçlü gruplara ayırır.

    Öncelik ikili gruplardadır; kalan tek bina oluşacaksa son grup üçlüye çevrilir.
    """
    ordered = list(ordered_ids)
    groups = []
    index = 0

    while index < len(ordered):
        remaining = len(ordered) - index
        if remaining == 3:
            groups.append(ordered[index:index + 3])
            break
        if remaining == 1 and groups:
            previous = groups.pop()
            groups.append(previous + ordered[index:index + 1])
            break
        if remaining == 1:
            groups.append(ordered[index:index + 1])
            break
        groups.append(ordered[index:index + 2])
        index += 2

    return groups


def build_group_nizam_configuration(
    record,
    adjacency,
    group_member_ids,
    setback_front,
    setback_side,
    setback_back,
    mode,
):
    """
    Bitişik / blok nizam için grup bazlı kenar setback listesini üretir.

    mode:
        - 'attached': tüm yan kenarlar 0 kabul edilir
        - 'block': grup içi paylaşılan yanlar 0, grup dışı açık yanlar setback_side
    """
    edge_count = len(record["edges"])
    front_indices = set(record["facade_indices"].get("front", []))
    back_indices = set(record["facade_indices"].get("back", []))
    attachable_indices = set(record["attachable_side_indices"])
    shared_with_group = set()

    for neighbor_id, info in adjacency.get(record["feature_id"], {}).items():
        if neighbor_id in group_member_ids:
            shared_with_group.add(info["self_edge"])

    edge_setbacks = [0.0] * edge_count
    adjustable_indices = set()

    for idx in range(edge_count):
        if idx in front_indices:
            edge_setbacks[idx] = setback_front
            adjustable_indices.add(idx)
            continue
        if idx in back_indices:
            edge_setbacks[idx] = setback_back
            adjustable_indices.add(idx)
            continue

        if idx in attachable_indices or idx not in front_indices.union(back_indices):
            if mode == "attached":
                edge_setbacks[idx] = 0.0
            elif idx in shared_with_group:
                edge_setbacks[idx] = 0.0
            else:
                edge_setbacks[idx] = setback_side
                adjustable_indices.add(idx)

    return {
        "edge_setbacks": edge_setbacks,
        "adjustable_indices": sorted(adjustable_indices),
    }
