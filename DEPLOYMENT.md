# 🚀 LTTS Deployment Guide - Render Platform

Complete deployment guide for the **Question Bank & Test Management System** on Render.

## 📋 Pre-Deployment Checklist

### ✅ Required Accounts & Services
- [ ] [Render.com](https://render.com) account created
- [ ] [Supabase](https://supabase.com) project set up
- [ ] GitHub repository with latest code
- [ ] Environment variables documented

### ✅ Local Testing (Required)
```bash
# Test frontend build
cd frontend
npm install
npm run build
npm run start:prod

# Test backend 
cd backend
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

## 🌐 Step 1: Supabase Setup

### 1.1 Get Supabase Credentials
1. Go to [Supabase Dashboard](https://app.supabase.com)
2. Navigate to **Project Settings > API**
3. Copy these values:
   - `Project URL` → `SUPABASE_URL`
   - `anon public` → `SUPABASE_ANON_KEY`
   - `service_role` → `SUPABASE_SERVICE_ROLE_KEY`

### 1.2 Get Database Connection String
1. Go to **Project Settings > Database**
2. Copy the connection string (URI format)
3. Replace `[YOUR-PASSWORD]` with your database password

---

## 🔧 Step 2: Environment Variables Setup

### 2.1 Backend Environment Variables (render.com dashboard)
```env
# Server Configuration
PORT=8000
HOST=0.0.0.0
ENVIRONMENT=production

# Supabase Configuration (No DATABASE_URL needed)
SUPABASE_URL=https://[PROJECT-ID].supabase.co
SUPABASE_SERVICE_KEY=[YOUR-SERVICE-ROLE-KEY]
SUPABASE_ANON_KEY=[YOUR-ANON-KEY]

# JWT Configuration  
JWT_SECRET_KEY=[GENERATE-STRONG-SECRET-256-BITS]
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# CORS (Update after frontend deployment)
CORS_ORIGINS=https://your-frontend-app.onrender.com
```

### 2.2 Frontend Environment Variables (render.com dashboard)
```env
# Next.js Configuration
NODE_ENV=production
PORT=3000

# Supabase (Public variables)
NEXT_PUBLIC_SUPABASE_URL=https://[PROJECT-ID].supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=[YOUR-ANON-KEY]

# Backend API (Update after backend deployment)
NEXT_PUBLIC_API_URL=https://your-backend-app.onrender.com
```

---

## 🚀 Step 3: Deploy to Render

### 3.1 Deploy Using render.yaml (Recommended)
1. Push `render.yaml` to your GitHub repository
2. Go to [Render Dashboard](https://dashboard.render.com)
3. Click **New** → **Blueprint**
4. Connect your GitHub repository
5. Render will automatically create both services

### 3.2 Manual Deployment (Alternative)

#### Deploy Backend Service
1. **New** → **Web Service**
2. **Settings:**
   - **Runtime:** Python
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Root Directory:** `backend`
   - **Health Check Path:** `/health`
3. Add all backend environment variables

#### Deploy Frontend Service  
1. **New** → **Web Service**
2. **Settings:**
   - **Runtime:** Node.js
   - **Build Command:** `npm install && npm run build`
   - **Start Command:** `npm run start:prod`
   - **Root Directory:** `frontend`
3. Add all frontend environment variables

---

## 🔗 Step 4: Configure Service URLs

### 4.1 Update Frontend Environment
After backend deploys, update frontend env vars:
```env
NEXT_PUBLIC_API_URL=https://ltts-backend-[random].onrender.com
```

### 4.2 Update Backend CORS
After frontend deploys, update backend env vars:
```env
CORS_ORIGINS=https://ltts-frontend-[random].onrender.com
```

---

## ✅ Step 5: Verification & Testing

### 5.1 Health Checks
- **Backend Health:** `https://your-backend.onrender.com/health`
- **Frontend:** `https://your-frontend.onrender.com`

### 5.2 Full System Test
1. **Authentication:** Register/login users
2. **Question Banks:** Upload CSV/Excel files
3. **Test Creation:** Create and publish tests
4. **Test Taking:** Take tests as student
5. **Analytics:** View dashboard analytics
6. **Sharing:** Generate and use test links

### 5.3 Monitor Logs
- Check Render service logs for errors
- Monitor database connections
- Verify API endpoints working

---

## 🛠️ Troubleshooting

### Common Issues & Fixes

#### Build Failures
```bash
# Clear Next.js cache locally
rm -rf .next
npm install
npm run build
```

#### Database Connection Issues
- Verify DATABASE_URL format
- Check Supabase project status
- Ensure IP allowlisting (if enabled)

#### CORS Errors
- Update CORS_ORIGINS with exact frontend URL
- Include both HTTP and HTTPS if testing

#### Environment Variable Issues
- Verify all required variables are set
- Check for typos in variable names
- Ensure secrets are properly encoded

---

## 🔐 Security Best Practices

### Production Hardening
- [ ] Use strong JWT_SECRET_KEY (256+ bits)
- [ ] Enable Supabase Row Level Security (RLS)
- [ ] Set proper CORS origins
- [ ] Monitor error logs for security issues
- [ ] Regularly update dependencies

### Environment Management  
- [ ] Never commit .env files
- [ ] Use Render's encrypted environment variables
- [ ] Rotate JWT secrets periodically
- [ ] Monitor Supabase usage and quotas

---

## 📊 Performance Optimization

### Render Service Scaling
- **Starter Plan:** Good for development/testing
- **Standard Plan:** Recommended for production
- **Pro Plan:** For high-traffic applications

### Database Optimization
- Monitor Supabase database performance
- Set up proper indexes for queries
- Consider read replicas for high load

---

## 🎯 Post-Deployment

### Custom Domains (Optional)
1. Purchase domain from provider
2. Add CNAME record pointing to Render
3. Configure SSL certificate
4. Update environment variables

### Monitoring & Alerts
- Set up Render service monitoring
- Configure Supabase alerts
- Monitor application logs
- Set up uptime monitoring

---

## 📞 Support & Resources

### Documentation Links
- [Render Documentation](https://render.com/docs)
- [Supabase Documentation](https://supabase.com/docs)
- [Next.js Deployment](https://nextjs.org/docs/deployment)
- [FastAPI Deployment](https://fastapi.tiangolo.com/deployment/)

### Emergency Contacts
- Render Support: [support@render.com](mailto:support@render.com)
- Supabase Support: [support@supabase.com](mailto:support@supabase.com)

---

**🎉 Congratulations! Your LTTS application should now be live on Render!**

Remember to test all functionality before announcing the deployment to users.
