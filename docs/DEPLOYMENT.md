# Deployment

## Vercel

ShelfSense AI can be deployed to Vercel as a FastAPI app. The root `main.py` exposes the FastAPI `app` object, and Vercel serves it through the Python runtime.

### Deploy From GitHub

1. Open Vercel.
2. Choose New Project.
3. Import `Ronnirvin2006/ShelfSense-AI-Retail-Shelf-Monitoring`.
4. Keep the framework as Other.
5. Configure persistent PostgreSQL through `DATABASE_URL`; startup fails on Vercel without it. Set `COOKIE_SECURE=1` and `SHELFSENSE_ORIGIN` to the HTTPS website origin.
6. Using the same database URL locally, run `python -m scripts.create_admin` to provision the first account.
7. Verify the hosting plan can package and run PyTorch, OpenCV, Ultralytics, and `models/best.pt` before deploying.

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

The application requires real model weights and persistent history. Vercel request limits may be lower than the application's 12 MB upload limit; consult [function limits](https://vercel.com/docs/functions/limitations). A successful local run is not deployment verification.

For sustained camera inference, use a persistent backend host. Run one worker for this release: inference locks, caches, login throttling, and task synchronization are process-local. Multiple concurrent workers need distributed coordination before production rollout. Use an HTTPS reverse proxy, `COOKIE_SECURE=1`, and `SHELFSENSE_ORIGIN` for remote access. Browser cameras require HTTPS or localhost.

PostgreSQL hosting, physical IP cameras, load capacity, and a live Vercel deployment still require testing in the target environment. See [operations setup](OPERATIONS.md).
