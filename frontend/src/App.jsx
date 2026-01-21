import { BrowserRouter, Routes, Route } from 'react-router-dom';
import OrderPage from './OrderPage';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* QR 코드를 찍으면 /order/{token} 주소로 들어옵니다 */}
        <Route path="/order/:token" element={<OrderPage />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;