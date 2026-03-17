import bpy
import json

# ─── НАСТРОЙКИ ────────────────────────────────────────────────────
OUTPUT_PATH = '/tmp/nodes_export.json'

# Оставь одно из трёх:
# 1) Конкретное имя материала
MATERIAL_NAME = None          # например: 'MyMaterial'
# 2) Конкретный GeoNodes-модификатор
MODIFIER_NAME = None          # например: 'GeometryNodes'
# 3) None + None → возьмёт первый материал активного объекта
# ──────────────────────────────────────────────────────────────────


def safe_value(v):
    """Конвертирует значение в JSON-сериализуемый тип."""
    if v is None:
        return None
    if isinstance(v, (int, float, bool, str)):
        return v
    try:
        return list(v)          # Vector, Color, etc.
    except TypeError:
        return str(v)


def export_node_tree(node_tree):
    nodes_data = []

    for node in node_tree.nodes:
        node_info = {
            "name":     node.name,
            "type":     node.type,
            "label":    node.label,
            "location": [node.location.x, node.location.y],
            "inputs":   [],
            "outputs":  [],
        }

        for inp in node.inputs:
            inp_data = {"name": inp.name, "type": inp.type, "linked": inp.is_linked}
            if hasattr(inp, 'default_value') and not inp.is_linked:
                try:
                    inp_data["value"] = safe_value(inp.default_value)
                except Exception:
                    pass
            node_info["inputs"].append(inp_data)

        for out in node.outputs:
            node_info["outputs"].append({"name": out.name, "type": out.type})

        # Дополнительные свойства нод
        for attr in ('operation', 'blend_type', 'data_type',
                     'noise_dimensions', 'interpolation', 'color_space',
                     'mapping', 'mode', 'musgrave_type', 'wave_type'):
            if hasattr(node, attr):
                node_info[attr] = str(getattr(node, attr))

        nodes_data.append(node_info)

    links_data = [
        {
            "from_node":   lnk.from_node.name,
            "from_socket": lnk.from_socket.name,
            "to_node":     lnk.to_node.name,
            "to_socket":   lnk.to_socket.name,
        }
        for lnk in node_tree.links
    ]

    return {"nodes": nodes_data, "links": links_data}


# ─── ПОЛУЧАЕМ NODE TREE ───────────────────────────────────────────
node_tree = None

if MODIFIER_NAME:
    obj = bpy.context.active_object
    if obj is None:
        raise RuntimeError("Нет активного объекта.")
    mod = obj.modifiers.get(MODIFIER_NAME)
    if mod is None:
        available = [m.name for m in obj.modifiers]
        raise KeyError(f"Модификатор '{MODIFIER_NAME}' не найден. Доступны: {available}")
    node_tree = mod.node_group

elif MATERIAL_NAME:
    mat = bpy.data.materials.get(MATERIAL_NAME)
    if mat is None:
        available = list(bpy.data.materials.keys())
        raise KeyError(f"Материал '{MATERIAL_NAME}' не найден. Доступны: {available}")
    node_tree = mat.node_tree

else:
    # Авто: первый материал активного объекта
    obj = bpy.context.active_object
    if obj is None or not obj.material_slots:
        # Запасной вариант — первый материал в сцене
        if bpy.data.materials:
            mat = bpy.data.materials[0]
            print(f"Авто-выбор материала: '{mat.name}'")
            node_tree = mat.node_tree
        else:
            raise RuntimeError("В сцене нет материалов.")
    else:
        mat = obj.material_slots[0].material
        print(f"Авто-выбор материала активного объекта: '{mat.name}'")
        node_tree = mat.node_tree

if node_tree is None:
    raise RuntimeError("Node tree не найден (материал без нод?).")

# ─── ЭКСПОРТ ─────────────────────────────────────────────────────
result = export_node_tree(node_tree)

with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
    json.dump(result, f, indent=2, ensure_ascii=False)

print(f"✓ Экспортировано {len(result['nodes'])} нод, "
      f"{len(result['links'])} связей → {OUTPUT_PATH}")
