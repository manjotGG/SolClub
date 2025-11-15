@echo off
title Real SolClub Demo - Production Solana Loyalty Program

echo.
echo ===============================================
echo   REAL SolClub - Production Demo
echo ===============================================
echo   Features:
echo   - Real blockchain transactions (devnet)
echo   - Real wallet integrations
echo   - Real NFT minting with metadata
echo   - Mystery NFT system with reveals
echo   - Seasonal collections
echo ===============================================
echo.

echo [1/3] Installing required packages...
pip install -r requirements.txt

echo.
echo [2/3] Running comprehensive demo...
python main.py demo

echo.
echo [3/3] Demo complete! Available commands:
echo   python main.py server  - Start backend API
echo   python main.py qr      - Generate QR codes
echo   python main.py mint    - Mint mystery NFTs
echo.
echo Then use your mobile wallet to scan the generated QR codes!
echo.

pause