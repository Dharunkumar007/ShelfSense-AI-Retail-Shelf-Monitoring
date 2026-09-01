# Deployment

## Vercel

ShelfSense AI can be deployed to Vercel as a FastAPI app. The root `main.py` exposes the FastAPI `app` object, and Vercel serves it through the Python runtime.

### Deploy From GitHub

1. Open Vercel.
2. Choose New Project.
3. Import `Ronnirvin2006/ShelfSense-AI-Retail-Shelf-Monitoring`.
4. Keep the framework as Other.
5. Deploy.

### Deploy From Terminal

```bash
cd /home/ron/dharun
npx vercel
```

For production:

```bash
npx vercel --prod
```

## App Integration

The website is also a PWA-style app. Users can open the deployed Vercel URL on mobile and install it from the browser menu. Both website and app screens use the same API routes:

- `/api/analyze`
- `/api/planogram`
- `/api/history`
- `/api/health`

## Production Note

The prototype uses mock AI detection and temporary scan history on Vercel. For final production, connect a hosted database and add a trained YOLOv8 model.
