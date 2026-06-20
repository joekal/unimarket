#!/bin/bash
# 🚀 Script d'optimisation serveur Django

echo "⚡ Optimisation serveur UniMarket..."

# Nettoyer le cache Python
echo "🧹 Cleaning Python cache..."
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true

# Vérifier les migrations
echo "📦 Applying migrations..."
python manage.py migrate --noinput

# Collecter les static files (avec cache-busting)
echo "📁 Collecting static files..."
python manage.py collectstatic --noinput --clear

# Nettoyer les sessions obsolètes
echo "🔄 Cleaning expired sessions..."
python manage.py clearsessions

# Compiler les messages (si i18n)
echo "🌐 Compiling messages..."
python manage.py compilemessages 2>/dev/null || true

echo ""
echo "✅ Optimisation terminée!"
echo ""
echo "🚀 Lancer le serveur:"
echo "   python manage.py runserver 0.0.0.0:8000"
echo ""
echo "💡 Pour plus de vitesse en dev:"
echo "   python manage.py runserver 0.0.0.0:8000 --noreload"
echo ""
