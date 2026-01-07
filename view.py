import socket
import json
import uuid
import os
import math
import base64
import hashlib
#👉 Đọc file theo từng khối nhỏ (chunk) 1024 byte, Mỗi lần trả ra 1 chunk, Dùng để gửi file qua UDP từng phần, không load cả file vào RAM.

#Định nghĩa một hàm: path: đường dẫn tới file (vd: "a.zip") chunk_size: kích thước mỗi mảnh (mặc định 1024 byte) offset: số thứ tự chunk hiện tại (ban đầu = 0)
def file_to_bytes(path, chunk_size=1024, offset=0):
    #Mở file ở chế độ read binary: đọc đúng byte gốc của file bắt buộc với file .zip, .png, .exe .with đảm bảo file tự đóng khi đọc xong.
    with open(path, "rb") as f:
        while True:
           # Di chuyển con trỏ đọc file tới vị trí:
            f.seek(offset*chunk_size)
            offset += 1
            chunk = f.read(chunk_size)
            #Khi không còn dữ liệu để đọc:thoát vòng lặp
            if not chunk:
                break
           # Trả về 1 chunk duy nhất, rồi: tạm dừng hàm ,nhớ trạng thái ,lần sau gọi → tiếp tục đọc chunk kế tiếp  Vì có yield → đây là generator function
            yield chunk

# def file_to_bytes1(path):
#     with open(path, "rb") as f:
#         chunk = f.read()
#         return chunk
            
# data = file_to_bytes1("duck.png")


#Đoạn này khởi tạo client UDP: biết gửi cho server nào ,tạo UDP socket, gán cổng nguồn ,đặt timeout để phát hiện mất gói
class Client: 
    #Hàm khởi tạo (constructor): server_ip: IP của server .server_port: port server đang lắng nghe. "127.0.0.1" = chính máy mình (loopback)
    def __init__(self, server_ip="127.0.0.1", server_port=9000):
        # Lưu địa chỉ Server (IP, port) để dùng cho sendto()
        #Dùng cho: sendto(data, self.server_addr) UDP không giữ kết nối, nên mỗi lần gửi phải biết rõ địa chỉ đích.
        self.server_addr = (server_ip, server_port)
         # Tạo socket UDP (SOCK_DGRAM) ipv4 và udp
        self.client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        #Bind client vào:"0.0.0.0" → tất cả interface mạng  .0 → OS tự cấp port ngẫu nhiên Mục đích:lient có cổng nguồn cố định trong suốt phiên        
        self.client.bind(("0.0.0.0", 0))
        # Thiết lập timeout cho recvfrom()
        #chờ tối đa 2 giây không nhận được ACK → timeout
        self.client.settimeout(2)

    #gửi packet UDP sang server
    #Nhận vào packet dạng dict .Packet này đã được client đóng gói (DATA / END / ERROR…)
    def send_message(self, dict):
    #Thực hiện 2 bước liên tiếp: json.dumps(dict) Chuyển dict → JSON string
    #Vì packet có nhiều trường: type, file_id, chunk_index, data…
    #.encode() Chuyển JSON string → bytes Vì UDP chỉ gửi được bytes Nếu thiếu .encode() → sendto() sẽ lỗi.
        message = json.dumps(dict).encode()
    #Gửi bytes tới:(server_ip, server_port) Đặc điểm UDP:Không cần connect, Mỗi lần gửi phải chỉ rõ địa chỉ đích, Gửi là xong, không biết server có nhận hay không
        self.client.sendto(message, self.server_addr)

#Hàm dùng để: chờ server trả lời, thường là ACK hoặc ERROR
    def receive_response(self):
        try:
            # Nhận phản hồi từ Server (ACK hoặc ERROR), chờ nhận tối đa 4096 byte
            data, addr = self.client.recvfrom(4096)
            #trả về: data: dữ liệu nhận được (bytes), addr: địa chỉ server gửi về
            return data, addr
        #Nếu quá thời gian chờ (settimeout(2)): Không nhận được phản hồi
        #Có thể do:gói DATA bị mất ,ACK bị mất ,trả về None để vòng lặp bên ngoài quyết định gửi lại
        except socket.timeout:
            return None, None
            
    def close(self):
        # Đóng socket UDP
        self.client.close()

def send_corrupted_packet(client, file_path, chunk_size=1024):
    # Gửi thử một gói DATA với checksum sai để server phản hồi ERROR
    with open(file_path, "rb") as f:
        byte_chunk = f.read(chunk_size)

    bad_data = bytearray(byte_chunk)
    if bad_data:
        bad_data[0] ^= 0xFF  # đảo 1 byte để tạo lỗi

    packet = {
        "type": "DATA",
        "file_id": str(uuid.uuid4()),
        "file_name": file_path,
        "chunk_index": 0,
        "total_chunks": 1,
        "chunk_size": len(bad_data),
        "data": base64.b64encode(bad_data).decode("ascii"),
        # Checksum cố ý sai
        "checksum": "INVALID_CHECKSUM",
    }
    client.send_message(packet)
    print("Đã gửi gói DATA lỗi giả lập (checksum sai)")

# Tạo đối tượng Client
client = Client()
# Đường dẫn file cần gửi
file_path = input("Nhập tên file: ")
# chunk_size xác định kích thước mỗi packet dữ liệu.
# Chia nhỏ giúp tránh packet quá lớn và dễ retransmit
chunk_size = 1024
# Số lần retry khi nhận ERROR hoặc timeout
MAX_RETRIES = 3
# Giả lập gói lỗi ở chunk thứ 2 (index 1) trong lần gửi đầu tiên
CORRUPT_CHUNK_INDEX = 1
# Tạo file_id duy nhất cho phiên truyền
# Giúp Server phân biệt nhiều file / nhiều client
file_id = str(uuid.uuid4())
# Lấy kích thước file để tính tổng chunk
file_size = os.path.getsize(file_path)
# Tổng số chunk của file
# (Mục đích: theo dõi tiến độ và hỗ trợ ráp file phía Server)
total_chunks = (file_size % chunk_size) + file_size - (file_size % chunk_size)
#tạo đối tựong băm SHA256(chunk1 + chunk2 + chunk3)
file_hasher = hashlib.sha256()

    # Mỗi vòng lặp tương ứng với một DATA packet.
    # i đóng vai trò là chunk_index – vị trí của mảnh dữ liệu trong file gốc.
for i, byte_chunk in enumerate(file_to_bytes(file_path, chunk_size)):
     # Cập nhật hash tổng file 
    file_hasher.update(byte_chunk)
    
    # Đóng gói DATA packet dưới dạng JSON
    packet =  {"type": "DATA", 
            # file_id giúp Server biết chunk này thuộc về file nào
            "file_id": file_id,
            # Tên file (để Server đặt tên file output)
            "file_name": file_path,
            # chunk_index là chìa khóa để Server ráp file đúng vị trí.
            # Điều này đặc biệt quan trọng vì UDP không đảm bảo thứ tự gói tin.
            "chunk_index": i,
            # Tổng số chunk của file
            # Giúp Server theo dõi tiến độ và kiểm tra thiếu chunk
            "total_chunks": total_chunks,
            # Kích thước thực tế của chunk (chunk cuối có thể nhỏ hơn)
            "chunk_size": len(byte_chunk),
            # data chứa nội dung chunk đã được mã hóa base64.
            # Việc encode là bắt buộc vì JSON không hỗ trợ dữ liệu nhị phân.
            "data": base64.b64encode(byte_chunk).decode("ascii"),
            # checksum là mã băm SHA-256 của chunk.
            # Server sẽ tính lại checksum để phát hiện lỗi dữ liệu.
            "checksum": base64.b64encode(
            hashlib.sha256(byte_chunk).digest()
        ).decode("ascii")}
    # print(byte_chunk)
    # print(base64.b64encode(byte_chunk))
    # print(base64.b64encode(byte_chunk).decode("ascii"))    

    # print(f"Gửi chunk {i+1}/{dict}")
    
    # Gửi DATA packet tới Server và xử lý retry khi có lỗi
    for attempt in range(1, MAX_RETRIES + 1):
        # Lần gửi đầu tiên của chunk thứ 2: gửi gói lỗi để server trả ERROR
        outgoing = packet
        if i == CORRUPT_CHUNK_INDEX and attempt == 1:
            corrupted_data = bytearray(byte_chunk)
            if corrupted_data:
                corrupted_data[0] ^= 0xFF
            outgoing = dict(packet)
            outgoing["data"] = base64.b64encode(corrupted_data).decode("ascii")
            outgoing["checksum"] = "INVALID_CHECKSUM"
            print("Gửi gói DATA lỗi giả lập cho chunk thứ 2")

        client.send_message(outgoing)
        data, addr = client.receive_response()

        if not data:
            print(f"Timeout – chưa nhận ACK (lần {attempt}/{MAX_RETRIES})")
            continue

        try:
            response = json.loads(data.decode())
        except json.JSONDecodeError:
            print(f"Phản hồi không phải JSON, gửi lại chunk {i} (lần {attempt}/{MAX_RETRIES})")
            continue

        # Nhận ACK -> thoát vòng lặp retry
        if response.get("type") == "ACK":
            print("Server trả:", response)
            break

        # Nhận ERROR -> gửi lại chunk
        if response.get("type") == "ERROR":
            print(f"Server báo lỗi cho chunk {i}, gửi lại (lần {attempt}/{MAX_RETRIES})")
            continue

        # Phản hồi không xác định -> thử gửi lại
        print(f"Phản hồi không xác định {response}, gửi lại chunk {i} (lần {attempt}/{MAX_RETRIES})")
    else:
        print(f"Chunk {i} gửi thất bại sau {MAX_RETRIES} lần thử")
    
dict = {# Gói END báo hiệu đã gửi xong toàn bộ chunk
        "type": "END",
        # Gắn với file_id của phiên truyền
        "file_id": file_id,
        # Checksum tổng của toàn bộ file
        # Server dùng để kiểm tra file sau khi ráp xon
        "file_checksum": base64.b64encode(file_hasher.digest()).decode("ascii"),
        # Trạng thái kết thúc
        "status": "finished"}
# print(file_hasher.digest())
# print(base64.b64encode(file_hasher.digest()).decode("ascii"))
# print(base64.b64encode(hashlib.sha256(data).digest()).decode("ascii"))
# Gửi gói END tới Server
client.send_message(dict)

# client.close()



