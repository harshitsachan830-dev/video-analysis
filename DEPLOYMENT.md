# Deployment

## Frontend — Vercel

1. Import this repository into Vercel and set the project root directory to `frontend`.
2. Add the `VITE_API_URL` environment variable, set to the public URL of the Render backend (for example, `https://video-analysis-api.onrender.com`).
3. Deploy the project. The Vercel settings in `frontend/vercel.json` use Vite and publish the `dist` directory.

## Backend — Render

1. Create a new Blueprint deployment from this repository and select the root `render.yaml`.
2. Deploy the `video-analysis-api` web service.
3. Copy the service's public URL into the Vercel `VITE_API_URL` setting, then redeploy the frontend so it uses the backend URL.

### Transcript provider

YouTube may block transcript requests from cloud server IP addresses. To retrieve existing captions through Supadata instead:

1. Create an account at [Supadata](https://dash.supadata.ai/) and copy the API key from its dashboard.
2. In Render, open the `video-analysis-api` service and add `SUPADATA_API_KEY` under **Environment**. Keep the key private; do not commit it or paste it into the frontend.
3. Save the change and wait for the backend to redeploy, then retry the video in the existing Vercel site.

When `SUPADATA_API_KEY` is set, the backend requests native transcripts only; it does not ask Supadata to generate captions with AI. Supadata currently charges one credit per native transcript request; check its dashboard for current plan limits and pricing. Without this setting, the backend continues to use its existing transcript-fetching methods.

Users add their Gemini API key in the app's **Add Gemini API key** settings. The key is saved in that browser's local storage, so it remains after refreshes and return visits on the same browser profile and device. It is sent to the backend with AI requests and is not persisted by the backend. Browser local storage is accessible to scripts running on the site and anyone with access to that browser profile; users should only save keys on trusted, private devices. The key does not sync to another browser or device. Users are responsible for their Gemini account's usage and any applicable charges. You can optionally configure a server-level `GEMINI_API_KEY` on Render as a fallback, but it is not required when users provide their own keys.

The included Render Blueprint uses the free plan. Free services can sleep when idle, have limited memory, and do not provide persistent disks. Transcript search uses lightweight keyword ranking instead of loading a local neural embedding model, to reduce backend memory use on the free plan. Keyword search is less semantically flexible than vector search. Indexed videos are still stored on local disk and can be lost when the service restarts, so the deployment is suitable for experimentation rather than durable storage or guaranteed uptime.
