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

# --- CÁC HÀM XỬ LÝ ---

def get_coords(address):
    """Chuyển địa chỉ thành tọa độ"""
    try:
        geolocator = Nominatim(user_agent="vrp_flask_app_v1")
        loc = geolocator.geocode(f"{address}, Ho Chi Minh, Vietnam")
        if loc: return loc.latitude, loc.longitude
    except:
        return None
    return None

def get_road_path(p1, p2):
    """Gọi API OSRM để lấy hình dạng đường đi (Geometry) để vẽ lên bản đồ"""
    # p1, p2 là (lat, lon) -> API cần (lon, lat)
    url = f"http://router.project-osrm.org/route/v1/driving/{p1[1]},{p1[0]};{p2[1]},{p2[0]}?overview=full"
    try:
        r = requests.get(url, timeout=4)
        if r.status_code == 200:
            data = r.json()
            if data['routes']:
                geom = data['routes'][0]['geometry']
                dist = data['routes'][0]['distance']
                return polyline.decode(geom), dist / 1000
    except Exception as e:
        print(f"Lỗi OSRM Route: {e}")
    # Fallback
    return [p1, p2], geodesic(p1, p2).km

def get_distance_matrix(nodes):
    """
    Tính ma trận khoảng cách giữa tất cả các điểm bằng OSRM Table API.
    Input: List các node (dict có lat, lon)
    Output: Mảng 2 chiều chứa khoảng cách km. Matrix[i][j] là từ điểm i đến điểm j.
    """
    # Tạo chuỗi tọa độ: lon1,lat1;lon2,lat2;...
    coords_str = ";".join([f"{n['lon']},{n['lat']}" for n in nodes])
    url = f"http://router.project-osrm.org/table/v1/driving/{coords_str}?annotations=distance"
    
    try:
        print("Đang gọi OSRM Matrix API...")
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            data = r.json()
            # OSRM trả về mét -> Chia 1000 ra km
            matrix_meters = data['distances']
            matrix_km = [[d / 1000.0 if d is not None else float('inf') for d in row] for row in matrix_meters]
            print("Đã lấy được Ma trận khoảng cách thực tế!")
            return matrix_km
    except Exception as e:
        print(f"Lỗi OSRM Matrix: {e}")

    # Fallback: Nếu API lỗi, tự tính thủ công bằng đường chim bay
    print("Dùng Geodesic thay thế...")
    n = len(nodes)
    matrix = [[0]*n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i != j:
                matrix[i][j] = geodesic((nodes[i]['lat'], nodes[i]['lon']), 
                                      (nodes[j]['lat'], nodes[j]['lon'])).km
    return matrix

def solve_greedy(address_list):
    # 1. Chuyển địa chỉ thành tọa độ và đánh số thứ tự
    nodes = [{'id': 0, 'name': DEPOT_NAME, 'lat': DEPOT_COORDS[0], 'lon': DEPOT_COORDS[1], 'type': 'depot'}]
    
    idx_counter = 1
    for addr in address_list:
        if addr.strip():
            co = get_coords(addr)
            if co:
                nodes.append({'id': idx_counter, 'name': addr, 'lat': co[0], 'lon': co[1], 'type': 'cust'})
                idx_counter += 1

    if len(nodes) < 2:
         return {'path': [], 'geometry': [], 'stats': {'km': 0, 'fuel': 0, 'time': 0}}

    # TÍNH MA TRẬN KHOẢNG CÁCH 
    dist_matrix = get_distance_matrix(nodes)

    # 2. Thuật toán Tham lam (Dùng Matrix)
    unvisited = nodes[1:] # List các khách hàng chưa đến
    curr_node = nodes[0]  # Đang ở Kho
    
    path_ordered = [curr_node]
    total_km = 0
    route_geometry = [] 

    print("--- Bắt đầu tìm đường ---")
    
    while unvisited:
        nearest = None
        min_dist = float('inf')
        
        curr_idx = curr_node['id'] # Lấy ID của điểm hiện tại (để tra bảng)

        # Tìm điểm gần nhất dựa trên MATRIX
        for node in unvisited:
            target_idx = node['id']
            # Tra bảng khoảng cách thực tế thay vì tính geodesic
            d = dist_matrix[curr_idx][target_idx]
            
            if d < min_dist:
                min_dist = d
                nearest = node
        
        # Di chuyển đến điểm tìm được
        if nearest:
            # Vẫn gọi hàm này để lấy hình dạng đường (vẽ lên map)
            road_path, road_dist = get_road_path((curr_node['lat'], curr_node['lon']), (nearest['lat'], nearest['lon']))
            
            route_geometry.extend(road_path)
            total_km += road_dist # Cộng dồn quãng đường
            
            path_ordered.append(nearest)
            unvisited.remove(nearest)
            curr_node = nearest

    # Quay về kho
    road_path, road_dist = get_road_path((curr_node['lat'], curr_node['lon']), DEPOT_COORDS)
    route_geometry.extend(road_path)
    total_km += road_dist
    path_ordered.append(nodes[0])

    # Tính toán chi phí
    fuel = (total_km / 100) * 2.5
    time = (total_km / 30) * 60

    return {
        'path': path_ordered,
        'geometry': route_geometry,
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