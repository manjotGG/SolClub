"""
Loyalty Dashboard
Web interface to view loyalty program statistics and user data
"""

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import json
import os
from datetime import datetime
from loyalty_engine import LoyaltyRulesEngine
from database.db import get_platform_stats, get_recent_cashback_events, get_recent_wallet_activity

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
        stats = get_platform_stats()
        stats["tier_distribution"] = stats.get("reward_breakdown", {})
        return stats
    except Exception as e:
        print(f"Error getting program stats: {e}")
        return {}

def get_recent_users(limit=10):
    """Get recently active users"""
    try:
        users = get_recent_wallet_activity(limit=limit)
        for user in users:
            user["tier"] = "active"
        return users
    except Exception as e:
        print(f"Error getting recent users: {e}")
        return []

def get_recent_rewards(limit=10):
    """Get recently awarded rewards"""
    try:
        return get_recent_cashback_events(limit=limit)
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