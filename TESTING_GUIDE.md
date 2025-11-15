# 🎯 SolClub Testing Guide - Complete Instructions

## 🚀 How to Run and Test Everything

### **Step 1: Setup (One-Time)**

1. **Install Python** (3.8+ required)
2. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Get a Solana Wallet** (for real testing):
   - Download **Phantom Wallet** on mobile
   - Switch to **Devnet** in settings
   - Get free devnet SOL: https://faucet.solana.com/

---

## 🎮 **Quick Start Options**

### **Option 1: One-Click Demo (Windows)**
```bash
# Double-click this file or run:
demo.bat
```

### **Option 2: Manual Commands**
```bash
# Run comprehensive demo
python main.py demo

# Start API server
python main.py server

# Interactive QR generator
python main.py qr

# Interactive NFT minter
python main.py mint
```

---

## 🧪 **Complete Testing Scenarios**

### **Test 1: Full System Demo**
```bash
python main.py demo
```
**What this does:**
- ✅ Generates real merchant wallet
- ✅ Creates actual Solana Pay QR codes
- ✅ Mints mystery NFTs with rarity system
- ✅ Shows seasonal collections
- ✅ Demonstrates all features working together

**Expected Output:**
- QR codes saved to `data/` folder
- NFT records in `data/real_nft_records.json`
- Wallet keypairs in `data/`

---

### **Test 2: API Server + Mobile Wallet Testing**

**Step 2a: Start Backend Server**
```bash
python main.py server
```
**Expected Output:**
```
🌐 Starting production API server...
📱 Ready for mobile wallet connections!
🔗 API Documentation: http://localhost:8000/docs
✨ This backend handles REAL Solana transactions!
INFO: Uvicorn running on http://0.0.0.0:8000
```

**Step 2b: Test API Endpoints**
Open browser to: http://localhost:8000/docs

**Available Endpoints:**
- `GET /` - API status
- `GET /solana-pay-request` - QR scan handler
- `POST /validate-transaction` - Transaction validation
- `POST /wallet-connect` - Wallet registration
- `GET /mystery-nft/{wallet}` - User's NFT collection
- `GET /seasonal-drops` - Active collections

**Step 2c: Test with Mobile Wallet**
1. Generate QR codes: `python main.py qr`
2. Scan QR with Phantom wallet
3. Approve transaction
4. Backend validates and mints NFT

---

### **Test 3: Interactive QR Code Generation**
```bash
python main.py qr
```

**Interactive Menu:**
```
QR Code Options:
1. Coffee Shop (0.01 SOL)
2. Bookstore (0.05 SOL) 
3. Electronics (0.1 SOL)
4. Custom amount
0. Exit
```

**What happens:**
- ✅ Creates real Solana Pay URLs
- ✅ Generates scannable QR codes
- ✅ Saves PNG files to data/ folder
- ✅ Works with ANY Solana wallet

**Example URLs Generated:**
```
solana:8t33iWFUfnMwEqJu5syy1eqJiocbNpYY7ax6ku4n3Xw2?amount=0.01&reference=abc123
```

---

### **Test 4: Interactive NFT Minting**
```bash
python main.py mint
```

**Interactive Process:**
1. Enter user wallet address
2. Choose NFT rarity:
   - Common Mystery (60% chance)
   - Rare Mystery (30% chance)
   - Epic Mystery (8% chance)
   - Legendary Mystery (2% chance)
   - Random (algorithmic distribution)

**What happens:**
- ✅ Mints real NFT with metadata
- ✅ Uploads to IPFS simulation
- ✅ 7-day reveal mechanism
- ✅ Seasonal themes applied
- ✅ Records saved to database

---

## 📱 **Mobile Wallet Testing (Real Transactions)**

### **Prerequisites:**
1. **Phantom Wallet** installed on mobile
2. **Devnet mode** enabled in wallet settings
3. **Devnet SOL** in wallet (from faucet)

### **Testing Process:**

**Step 1: Generate QR Code**
```bash
python main.py qr
# Select option 1 (Coffee Shop)
```

**Step 2: Start Backend**
```bash
# In another terminal:
python main.py server
```

**Step 3: Mobile Wallet Test**
1. 📸 **Scan QR** with Phantom
2. ✅ **Approve transaction** in wallet
3. 🎁 **Check backend logs** for NFT minting
4. 📊 **View API response** at http://localhost:8000/mystery-nft/YOUR_WALLET

**Expected Flow:**
```
Mobile Wallet → Scan QR → Approve TX → Backend Validates → NFT Minted → User Receives NFT
```

---

## 🔧 **Advanced Testing**

### **Test 5: API Testing with Curl**
```bash
# Test API status
curl http://localhost:8000

# Test wallet connection
curl -X POST http://localhost:8000/wallet-connect \
  -H "Content-Type: application/json" \
  -d '{"publicKey":"YOUR_WALLET_ADDRESS"}'

# Check user NFTs
curl http://localhost:8000/mystery-nft/YOUR_WALLET_ADDRESS

# View seasonal drops
curl http://localhost:8000/seasonal-drops
```

### **Test 6: Database Verification**
```bash
# Check generated files
dir data\

# View NFT records
type data\real_nft_records.json

# View merchant wallet
type data\merchant_keypair.json
```

---

## 📊 **Expected Test Results**

### **File Generation:**
```
data/
├── merchant_keypair.json        # Merchant wallet credentials
├── nft_minter_keypair.json     # NFT minting wallet  
├── real_nft_records.json       # NFT collection database
├── real_transactions.json      # Transaction history
├── loyalty_users.json          # User registrations
└── *.png                       # Generated QR codes
```

### **QR Code Testing:**
- ✅ QR codes scan with mobile wallets
- ✅ Generate valid Solana Pay URLs
- ✅ Include proper amount and reference
- ✅ Connect to merchant wallet

### **NFT Minting Results:**
- ✅ 4 rarity tiers with correct distribution
- ✅ Mystery metadata with reveal dates
- ✅ Seasonal themes when applicable
- ✅ Unique mint addresses generated
- ✅ Proper JSON structure

### **API Testing Results:**
- ✅ All endpoints return valid JSON
- ✅ CORS enabled for wallet connections
- ✅ Error handling works properly
- ✅ Documentation accessible at /docs

---

## 🆘 **Troubleshooting**

### **Common Issues & Solutions:**

**"No module named 'solders'"**
```bash
pip install solders
```

**"Transaction not found"**
- Wait 10-15 seconds for blockchain confirmation
- Check devnet status

**"Insufficient funds"**
- Get devnet SOL: https://faucet.solana.com/
- Ensure wallet is on devnet

**"QR code not scanning"**  
- Ensure wallet is on devnet mode
- Check QR code image quality
- Try different Solana wallet

**"Server won't start"**
```bash
# Check if port is in use
netstat -an | findstr :8000

# Kill existing process
taskkill /f /im python.exe
```

**"Files not generating"**
- Check folder permissions
- Ensure data/ directory exists
- Run as administrator if needed

---

## 🎯 **Testing Checklist**

### **Basic Tests:**
- [ ] `python main.py demo` runs successfully
- [ ] QR codes generated in data/ folder
- [ ] NFT records created in JSON files
- [ ] Backend server starts on port 8000

### **Integration Tests:**
- [ ] QR codes scan with mobile wallet
- [ ] API endpoints return valid responses
- [ ] NFT minting creates unique addresses
- [ ] Database files update correctly

### **Mobile Wallet Tests:**
- [ ] Phantom wallet connects to devnet
- [ ] QR code transactions approved
- [ ] Backend receives transaction data
- [ ] NFTs appear in user collection

### **Production Readiness:**
- [ ] Error handling works properly
- [ ] API documentation accessible
- [ ] All features demonstrated
- [ ] Clean file structure maintained

---

## 🏆 **Success Criteria**

**✅ You'll know it's working when:**

1. **Demo runs completely** without errors
2. **QR codes are scannable** with mobile wallets  
3. **Backend API responds** to all endpoints
4. **NFTs are minted** with proper metadata
5. **Files are generated** in data/ directory
6. **Mobile transactions work** end-to-end

**🎪 Ready to test the real blockchain magic!**

---

## 🚀 **Quick Commands Summary**

```bash
# Full demo
python main.py demo

# Start server  
python main.py server

# Generate QR codes
python main.py qr

# Mint NFTs
python main.py mint

# Help
python main.py help

# Windows one-click
demo.bat
```

**🎯 This is a complete, working Solana loyalty program ready for production testing!**