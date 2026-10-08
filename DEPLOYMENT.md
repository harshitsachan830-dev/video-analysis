# Deployment

## Frontend — Vercel

1. Import this repository into Vercel and set the project root directory to `frontend`.
2. Add the `VITE_API_URL` environment variable, set to the public URL of the Render backend (for example, `https://video-analysis-api.onrender.com`).
3. Deploy the project. The Vercel settings in `frontend/vercel.json` use Vite and publish the `dist` directory.

## Backend — Render

1. Create a new Blueprint deployment from this repository and select the root `render.yaml`.
2. Deploy the `video-analysis-api` web service. The Docker build preloads the embedding model because the backend requires it to already exist locally.
3. Copy the service's public URL into the Vercel `VITE_API_URL` setting, then redeploy the frontend so it uses the backend URL.

Users add their Gemini API key in the app's **Add Gemini API key** settings. The key is kept in page memory only, sent to the backend with AI requests, used by the backend to authenticate with Google Gemini, and not persisted by the app. Users are responsible for their Gemini account's usage and any applicable charges. You can optionally configure a server-level `GEMINI_API_KEY` on Render as a fallback, but it is not required when users provide their own keys.

The included Render Blueprint uses the free plan. Free services can sleep when idle, have limited memory, and do not provide persistent disks. This backend loads a PyTorch embedding model on startup and stores indexed videos on local disk, so the free instance may run out of memory and newly indexed data can be lost when the service restarts. The deployment is suitable for experimentation, not durable storage or guaranteed uptime.
