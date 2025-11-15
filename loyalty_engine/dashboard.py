"""
Loyalty Dashboard
Web interface to view loyalty program statistics and user data
"""

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import json
import os
import sqlite3
from datetime import datetime
from loyalty_engine import LoyaltyRulesEngine

app = FastAPI(title="SolClub Loyalty Dashboard")
templates = Jinja2Templates(directory="templates")

# Initialize loyalty engine
loyalty_engine = LoyaltyRulesEngine()

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard"""
    try:
        # Get overall statistics
        stats = get_program_stats()
        
        # Get recent activity
        recent_users = get_recent_users(limit=10)
        recent_rewards = get_recent_rewards(limit=10)
        
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "stats": stats,
            "recent_users": recent_users,
            "recent_rewards": recent_rewards
        })
    except Exception as e:
        return f"Dashboard Error: {str(e)}"

@app.get("/user/{wallet}", response_class=HTMLResponse)
async def user_profile(request: Request, wallet: str):
    """User profile page"""
    try:
        user_stats = loyalty_engine.get_user_stats(wallet)
        return templates.TemplateResponse("user_profile.html", {
            "request": request,
            "wallet": wallet,
            "user": user_stats
        })
    except Exception as e:
        return f"User Profile Error: {str(e)}"

@app.get("/api/stats")
async def api_stats():
    """API endpoint for program statistics"""
    try:
        return get_program_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/user/{wallet}")
async def api_user(wallet: str):
    """API endpoint for user data"""
    try:
        return loyalty_engine.get_user_stats(wallet)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def get_program_stats():
    """Get overall program statistics"""
    try:
        if loyalty_engine.use_sqlite:
            conn = sqlite3.connect(loyalty_engine.db_path)
            cursor = conn.cursor()
            
            # Get user count
            cursor.execute("SELECT COUNT(*) FROM users")
            total_users = cursor.fetchone()[0]
            
            # Get total transactions
            cursor.execute("SELECT SUM(total_transactions) FROM users")
            total_transactions = cursor.fetchone()[0] or 0
            
            # Get total rewards
            cursor.execute("SELECT COUNT(*) FROM rewards")
            total_rewards = cursor.fetchone()[0]
            
            # Get reward breakdown
            cursor.execute('''
                SELECT reward_type, COUNT(*) 
                FROM rewards 
                GROUP BY reward_type
            ''')
            reward_breakdown = dict(cursor.fetchall())
            
            # Get tier distribution
            cursor.execute('''
                SELECT tier, COUNT(*) 
                FROM users 
                GROUP BY tier
            ''')
            tier_distribution = dict(cursor.fetchall())
            
            conn.close()
            
            return {
                "total_users": total_users,
                "total_transactions": total_transactions,
                "total_rewards": total_rewards,
                "reward_breakdown": reward_breakdown,
                "tier_distribution": tier_distribution
            }
        else:
            # JSON file implementation
            if os.path.exists(loyalty_engine.json_file):
                with open(loyalty_engine.json_file, 'r') as f:
                    data = json.load(f)
                
                users = data.get("users", {})
                total_users = len(users)
                total_transactions = sum(user.get("total_transactions", 0) for user in users.values())
                total_rewards = sum(user.get("total_rewards", 0) for user in users.values())
                
                return {
                    "total_users": total_users,
                    "total_transactions": total_transactions,
                    "total_rewards": total_rewards,
                    "reward_breakdown": {},
                    "tier_distribution": {}
                }
            else:
                return {
                    "total_users": 0,
                    "total_transactions": 0,
                    "total_rewards": 0,
                    "reward_breakdown": {},
                    "tier_distribution": {}
                }
    except Exception as e:
        print(f"Error getting program stats: {e}")
        return {}

def get_recent_users(limit=10):
    """Get recently active users"""
    try:
        if loyalty_engine.use_sqlite:
            conn = sqlite3.connect(loyalty_engine.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT wallet_address, total_transactions, tier, last_activity
                FROM users 
                ORDER BY last_activity DESC 
                LIMIT ?
            ''', (limit,))
            
            users = cursor.fetchall()
            conn.close()
            
            return [
                {
                    "wallet": user[0],
                    "transactions": user[1],
                    "tier": user[2],
                    "last_activity": user[3]
                }
                for user in users
            ]
        else:
            return []
    except Exception as e:
        print(f"Error getting recent users: {e}")
        return []

def get_recent_rewards(limit=10):
    """Get recently awarded rewards"""
    try:
        if loyalty_engine.use_sqlite:
            conn = sqlite3.connect(loyalty_engine.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT r.wallet_address, r.reward_name, r.reward_type, r.earned_at
                FROM rewards r
                ORDER BY r.earned_at DESC 
                LIMIT ?
            ''', (limit,))
            
            rewards = cursor.fetchall()
            conn.close()
            
            return [
                {
                    "wallet": reward[0],
                    "reward_name": reward[1],
                    "reward_type": reward[2],
                    "earned_at": reward[3]
                }
                for reward in rewards
            ]
        else:
            return []
    except Exception as e:
        print(f"Error getting recent rewards: {e}")
        return []

# Create templates directory and basic HTML templates
def create_templates():
    """Create basic HTML templates"""
    templates_dir = "templates"
    os.makedirs(templates_dir, exist_ok=True)
    
    # Dashboard template
    dashboard_html = '''
<!DOCTYPE html>
<html>
<head>
    <title>SolClub Loyalty Dashboard</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .header { background: #8B5CF6; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .stat-card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .stat-number { font-size: 2em; font-weight: bold; color: #8B5CF6; }
        .recent-section { background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
        .user-item, .reward-item { padding: 10px; border-bottom: 1px solid #eee; }
        .wallet { font-family: monospace; color: #666; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🎯 SolClub Loyalty Dashboard</h1>
        <p>Real-time loyalty program analytics</p>
    </div>
    
    <div class="stats-grid">
        <div class="stat-card">
            <div class="stat-number">{{ stats.total_users }}</div>
            <div>Total Users</div>
        </div>
        <div class="stat-card">
            <div class="stat-number">{{ stats.total_transactions }}</div>
            <div>Total Transactions</div>
        </div>
        <div class="stat-card">
            <div class="stat-number">{{ stats.total_rewards }}</div>
            <div>Rewards Issued</div>
        </div>
    </div>
    
    <div class="recent-section">
        <h2>👥 Recent Users</h2>
        {% for user in recent_users %}
        <div class="user-item">
            <strong>{{ user.tier }}</strong> - 
            <span class="wallet">{{ user.wallet[:16] }}...</span> - 
            {{ user.transactions }} transactions
        </div>
        {% endfor %}
    </div>
    
    <div class="recent-section">
        <h2>🎁 Recent Rewards</h2>
        {% for reward in recent_rewards %}
        <div class="reward-item">
            <strong>{{ reward.reward_name }}</strong> - 
            <span class="wallet">{{ reward.wallet[:16] }}...</span> - 
            {{ reward.earned_at[:10] }}
        </div>
        {% endfor %}
    </div>
</body>
</html>
    '''
    
    with open(f"{templates_dir}/dashboard.html", 'w') as f:
        f.write(dashboard_html)
    
    print("✅ Dashboard templates created")

if __name__ == "__main__":
    import uvicorn
    
    # Create templates
    create_templates()
    
    print("🚀 Starting SolClub Loyalty Dashboard...")
    print("🌐 Dashboard available at: http://localhost:8001")
    uvicorn.run(app, host="0.0.0.0", port=8001)