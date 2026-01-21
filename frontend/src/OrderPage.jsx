import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import axios from 'axios';

function OrderPage() {
  const { token } = useParams(); // URL에서 토큰 가져오기
  const [store, setStore] = useState(null);
  const [tableInfo, setTableInfo] = useState(null);
  const [cart, setCart] = useState({}); // 장바구니 { 메뉴ID: 개수 }

  // 1. 화면이 켜지면 백엔드에서 정보 가져오기
  useEffect(() => {
    async function fetchData() {
      try {
        // A. 토큰으로 "이게 어느 가게지?" 확인
        const tableRes = await axios.get(`http://127.0.0.1:8000/tables/by-token/${token}`);
        setTableInfo(tableRes.data);

        // B. 가게 ID를 알았으니 "메뉴판" 가져오기
        const storeRes = await axios.get(`http://127.0.0.1:8000/stores/${tableRes.data.store_id}`);
        setStore(storeRes.data);
      } catch (error) {
        alert("유효하지 않은 QR 코드이거나 가게 정보를 불러올 수 없습니다.");
        console.error(error);
      }
    }
    fetchData();
  }, [token]);

  // 2. 장바구니 담기 함수
  const addToCart = (menuId) => {
    setCart(prev => ({
      ...prev,
      [menuId]: (prev[menuId] || 0) + 1
    }));
  };

  // 3. 주문하기 함수 (아직 콘솔에만 출력)
  const placeOrder = () => {
    const orderItems = Object.entries(cart).map(([menuId, qty]) => ({
        menu_id: parseInt(menuId),
        quantity: qty
    }));
    
    if (orderItems.length === 0) return alert("메뉴를 선택해주세요!");
    
    // 다음 단계에서 실제 주문 API를 연결할 예정입니다.
    console.log("주문 데이터:", {
        store_id: tableInfo.store_id,
        table_id: tableInfo.table_id,
        items: orderItems
    });
    alert("주문이 전송되었습니다! (콘솔 확인)");
  };

  if (!store || !tableInfo) return <div>메뉴판 로딩중...</div>;

  return (
    <div style={{ padding: '20px', maxWidth: '600px', margin: '0 auto' }}>
      <h1>🏠 {store.name}</h1>
      <p>📍 좌석: {tableInfo.label}</p>
      <hr />
      
      {/* 카테고리별 메뉴 리스트 */}
      {store.categories.map(cat => (
        <div key={cat.id}>
          <h3>📂 {cat.name}</h3>
          <ul style={{ listStyle: 'none', padding: 0 }}>
            {cat.menus.map(menu => (
              <li key={menu.id} style={{ borderBottom: '1px solid #ddd', padding: '10px 0', display: 'flex', justifyContent: 'space-between' }}>
                <div>
                  <strong>{menu.name}</strong>
                  <div style={{ color: '#888' }}>{menu.price}원</div>
                </div>
                <div>
                   {/* 장바구니 버튼 */}
                  <button onClick={() => addToCart(menu.id)} style={{ padding: '5px 10px' }}>
                    담기 (+{cart[menu.id] || 0})
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </div>
      ))}

      {/* 하단 주문 버튼 */}
      <div style={{ position: 'fixed', bottom: 0, left: 0, width: '100%', padding: '20px', background: 'white', borderTop: '1px solid #ccc' }}>
        <button 
            onClick={placeOrder}
            style={{ width: '100%', padding: '15px', background: 'orange', color: 'white', border: 'none', fontSize: '18px', fontWeight: 'bold' }}>
          주문하기
        </button>
      </div>
    </div>
  );
}

export default OrderPage;