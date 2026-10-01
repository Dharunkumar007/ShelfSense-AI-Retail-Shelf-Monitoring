# Implementation Status

Updated 1 October 2026. Implemented does not mean verified for production deployment.

## Implemented Locally

- Responsive website and installable PWA using the same API.
- Real YOLO inference, per-image zone charts, model/settings metadata, confidence/IoU/resolution/area controls, optional contrast, image-quality warnings, bounded inference caching.
- Persistent scan history, source filters, before/after comparison, CSV export, print reports.
- Browser camera and configured HTTP snapshot camera paths; two-observation task confirmation.
- Restock ownership, task states, completion notes, activity records.
- Shelf layout editing, thresholds, accounts, role permissions, session login, local-only initial setup.
- Empty current inspection on page load, even when history exists. Saved records open only through an explicit selection. This does not delete history, tasks, or inventory configuration.
- Product confidence tooltip on hover, keyboard focus, or tap. Zone overlays no longer block product interaction. Confidence is distinct from zone availability.
- Original user-supplied logo, blue/neutral palette, dark/light themes, saved theme preference, square reveal transition, scroll progress, upload-button ripple, semantic status alerts, reduced-motion handling.
- Project Terms of Service and Privacy Policy pages; these need operator-specific review before commercial publication.

## Implementation Choices

The frontend is plain HTML/CSS/JavaScript. The requested [Magic UI theme](https://magicui.design/docs/components/animated-theme-toggler), [scroll progress](https://magicui.design/docs/components/scroll-progress), and [ripple](https://magicui.design/docs/components/ripple-button) interactions are implemented natively. React imports and registry aliases cannot run directly in this stack. No React, Tailwind, or npm build step was introduced. Alerts follow the icon, semantic color, and message pattern shown by [daisyUI](https://daisyui.com/components/alert/); daisyUI is not installed.

The View Transitions API provides the square theme reveal. Unsupported browsers and reduced-motion preferences use an immediate theme switch. System fonts and tabular numerals avoid an external font download. The supplied logo is retained without image editing.

## Still Requires Target-System Verification

- Store-specific labelled validation, threshold selection, held-out accuracy measurements, and product/SKU recognition beyond generic item detection.
- Physical IP cameras and their network access; RTSP ingestion is not implemented.
- Hosted PostgreSQL, a live HTTPS/Vercel deployment, deployment size limits, backups, and restore drills.
- Fresh Windows installation and installed-PWA checks on actual phones.
- Concurrency and sustained-load testing. Process-local locks are not a distributed job queue.

## Not Implemented

- Multi-store isolation or separate planograms per camera.
- Email/SMS/push notifications, POS integrations, sales-risk estimation.
- Manual detection correction, model retraining feedback, account recovery, self-service deletion.

See [Operations](OPERATIONS.md), [Setup](SETUP_AND_LAUNCH.md), and [Deployment](DEPLOYMENT.md) for supported workflows. The older UI content plan is a historical proposal; use this document for current status.
