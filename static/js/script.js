document.addEventListener('DOMContentLoaded', function() {
    // ... (Phần khởi tạo bản đồ giữ nguyên) ...
    var map = L.map('map').setView([10.801869, 106.714263], 13);
    
    L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
        subdomains: 'abcd',
        maxZoom: 20
    }).addTo(map);

    var routeLayer = L.layerGroup().addTo(map);
    var depotIcon = L.icon({ iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-red.png', iconSize: [25, 41], iconAnchor: [12, 41] });
    var custIcon = L.icon({ iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-blue.png', iconSize: [25, 41], iconAnchor: [12, 41] });

    L.marker([10.801869, 106.714263], {icon: depotIcon}).addTo(map).bindPopup("<b>KHO HUTECH</b>").openPopup();

    // --- BIẾN TOÀN CỤC ĐỂ LƯU DỮ LIỆU ĐƯỜNG ĐI ---
    var currentPathData = []; 

    // Gán sự kiện
    document.getElementById('btn-add').addEventListener('click', addInput);
    document.getElementById('btn-calc').addEventListener('click', calculateRoute);
    
    // --- MỚI: Gán sự kiện cho nút Google Maps ---
    document.getElementById('btn-google').addEventListener('click', openGoogleMaps);


    // --- CÁC HÀM XỬ LÝ ---

    function addInput() {
        var div = document.createElement('div');
        div.innerHTML = '<input type="text" class="addr-input" placeholder="Nhập địa chỉ khách tiếp theo...">';
        document.getElementById('inputs').appendChild(div);
    }

    async function calculateRoute() {
        var inputs = document.getElementsByClassName('addr-input');
        var addresses = [];
        for (var i = 0; i < inputs.length; i++) {
            if(inputs[i].value) addresses.push(inputs[i].value);
        }

        if (addresses.length === 0) { alert("Vui lòng nhập ít nhất 1 địa chỉ!"); return; }

        // UI Loading
        document.getElementById('loading').style.display = 'block';
        document.getElementById('result-box').style.display = 'none'; // Ẩn kết quả cũ
        
        // --- MỚI: Ẩn nút Google Maps khi bắt đầu tính lại ---
        document.getElementById('btn-google').style.display = 'none';
        
        routeLayer.clearLayers();

        try {
            let response = await fetch('/calculate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ addresses: addresses })
            });
            
            let data = await response.json();
            
            // --- MỚI: Lưu dữ liệu đường đi để dùng cho nút Google Maps ---
            currentPathData = data.path; 

            // Cập nhật UI
            document.getElementById('loading').style.display = 'none';
            document.getElementById('result-box').style.display = 'block';
            
            // --- MỚI: Hiện nút Google Maps ---
            document.getElementById('btn-google').style.display = 'flex';

            document.getElementById('val-km').innerText = data.stats.km;
            document.getElementById('val-fuel').innerText = data.stats.fuel;
            document.getElementById('val-time').innerText = data.stats.time;

            // Vẽ Marker & Logs (Giữ nguyên)
            var logsHTML = "";
            data.path.forEach((node, index) => {
                if (node.type === 'cust') {
                    L.marker([node.lat, node.lon], {icon: custIcon})
                        .addTo(routeLayer)
                        .bindPopup(`<b>${index}. ${node.name}</b>`);
                }
                logsHTML += `<div class="log-item">➡️ ${index}. ${node.name}</div>`;
            });
            document.getElementById('route-logs').innerHTML = logsHTML;

            if (data.geometry && data.geometry.length > 0) {
                var polyline = L.polyline(data.geometry, {color: 'blue', weight: 5, opacity: 0.7}).addTo(routeLayer);
                map.fitBounds(polyline.getBounds());
            }

        } catch (error) {
            alert("Lỗi kết nối Server!");
            console.error(error);
            document.getElementById('loading').style.display = 'none';
        }
    }

    // --- MỚI: Hàm xử lý mở Google Maps ---
    function openGoogleMaps() {
        if (!currentPathData || currentPathData.length < 2) {
            alert("Chưa có dữ liệu lộ trình!");
            return;
        }

        // Lấy điểm xuất phát (Kho)
        var originNode = currentPathData[0];
        var origin = `${originNode.lat},${originNode.lon}`;

        // Lấy điểm đích (Thường là quay về Kho hoặc điểm cuối cùng)
        var destNode = currentPathData[currentPathData.length - 1];
        var destination = `${destNode.lat},${destNode.lon}`;

        // Lấy các điểm trung gian (Waypoints) - Bỏ điểm đầu và điểm cuối
        var waypoints = [];
        for (var i = 1; i < currentPathData.length - 1; i++) {
            waypoints.push(`${currentPathData[i].lat},${currentPathData[i].lon}`);
        }

        // Tạo URL
        var url = `https://www.google.com/maps/dir/?api=1&origin=${origin}&destination=${destination}`;
        
        if (waypoints.length > 0) {
            url += `&waypoints=${waypoints.join('|')}`;
        }
        
        url += `&travelmode=driving`; // Chế độ lái xe

        // Mở tab mới
        window.open(url, '_blank');
    }
});