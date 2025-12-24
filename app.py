from flask import Flask, render_template, request, jsonify
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import requests
import polyline

app = Flask(__name__)

# --- CẤU HÌNH ---
# Tọa độ mặc định: HUTECH
DEPOT_COORDS = (10.801869, 106.714263)
DEPOT_NAME = "KHO HUTECH (475A Điện Biên Phủ)"

# --- HÀM XỬ LÝ (GIỐNG CODE CŨ NHƯNG GÓI LẠI) ---
def get_coords(address):
    try:
        geolocator = Nominatim(user_agent="vrp_flask_app_v1")
        loc = geolocator.geocode(f"{address}, Ho Chi Minh, Vietnam")
        if loc: return loc.latitude, loc.longitude
    except:
        return None
    return None

def get_road_path(p1, p2):
    """Gọi API OSRM để lấy đường nhựa"""
    # URL API OSRM (Public)
    url = f"http://router.project-osrm.org/route/v1/driving/{p1[1]},{p1[0]};{p2[1]},{p2[0]}?overview=full"
    try:
        r = requests.get(url, timeout=4) # Tăng timeout lên 4s
        if r.status_code == 200:
            data = r.json()
            if data['routes']:
                # Giải mã polyline thành danh sách tọa độ
                geom = data['routes'][0]['geometry']
                dist = data['routes'][0]['distance']
                return polyline.decode(geom), dist / 1000
    except Exception as e:
        print(f"Lỗi OSRM: {e}")
    
    # Nếu lỗi thì trả về đường thẳng (fallback)
    return [p1, p2], geodesic(p1, p2).km

def solve_greedy(address_list):
    # 1. Chuyển địa chỉ thành tọa độ
    nodes = [{'name': DEPOT_NAME, 'lat': DEPOT_COORDS[0], 'lon': DEPOT_COORDS[1], 'type': 'depot'}]
    
    for addr in address_list:
        if addr.strip():
            co = get_coords(addr)
            if co:
                nodes.append({'name': addr, 'lat': co[0], 'lon': co[1], 'type': 'cust'})

    # 2. Thuật toán Tham lam
    unvisited = nodes[1:] # Bỏ kho ra
    curr_node = nodes[0]  # Bắt đầu tại kho
    
    path_ordered = [curr_node]
    total_km = 0
    route_geometry = [] # Chứa tọa độ để vẽ đường

    print("--- Bắt đầu tìm đường ---")
    
    # Vòng lặp đi qua các điểm
    while unvisited:
        nearest = None
        min_dist = float('inf')
        
        # Tìm điểm gần nhất (Chim bay)
        for node in unvisited:
            d = geodesic((curr_node['lat'], curr_node['lon']), (node['lat'], node['lon'])).km
            if d < min_dist:
                min_dist = d
                nearest = node
        
        # Di chuyển
        if nearest:
            # Lấy đường nhựa từ curr -> nearest
            road_path, road_dist = get_road_path((curr_node['lat'], curr_node['lon']), (nearest['lat'], nearest['lon']))
            
            route_geometry.extend(road_path) # Nối đường vào bản đồ
            total_km += road_dist
            
            path_ordered.append(nearest)
            unvisited.remove(nearest)
            curr_node = nearest

    # Quay về kho
    road_path, road_dist = get_road_path((curr_node['lat'], curr_node['lon']), DEPOT_COORDS)
    route_geometry.extend(road_path)
    total_km += road_dist
    path_ordered.append(nodes[0]) # Thêm kho vào cuối

    # Tính toán chi phí
    fuel = (total_km / 100) * 2.5
    time = (total_km / 30) * 60

    return {
        'path': path_ordered,
        'geometry': route_geometry, # Dữ liệu vẽ đường ngoằn ngoèo
        'stats': {'km': round(total_km, 2), 'fuel': round(fuel, 2), 'time': round(time, 0)}
    }

# --- ROUTING FLASK ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/calculate', methods=['POST'])
def calculate():
    data = request.json
    addresses = data.get('addresses', [])
    result = solve_greedy(addresses)
    return jsonify(result)

if __name__ == '__main__':
    app.run(debug=True, port=5000)