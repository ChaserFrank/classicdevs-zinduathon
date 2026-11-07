import { useState } from 'react'
import {Routes, Route, BrowserRouter} from 'react-router-dom'
import ContactUs from './pages/ContactUs'
import AboutUs from './pages/AboutUs' 
import Login from './pages/Login'
import Passwordrest from './pages/Passwordrest'
import LandingPage from './pages/LandingPage'

function App() {
  return (
    <>
    <BrowserRouter>
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/about" element={<AboutUs />} />
      <Route path="/contact" element={<ContactUs />} />
      <Route path="/login" element={<Login />} />
      <Route path="/passwordreset" element={<Passwordrest />} />
    </Routes>
    </BrowserRouter>
    </>
  )
}

export default App
