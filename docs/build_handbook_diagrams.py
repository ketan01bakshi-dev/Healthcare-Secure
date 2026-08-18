"""Generate PNG diagrams for Healthcare Secure handbook."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

OUT = Path(__file__).resolve().parent / "handbook_assets"
OUT.mkdir(parents=True, exist_ok=True)


def save(fig, name: str) -> None:
    fig.savefig(
        OUT / name,
        dpi=200,
        bbox_inches="tight",
        facecolor="white",
        edgecolor="none",
    )
    plt.close(fig)
    print("wrote", name)


def box(ax, x, y, w, h, text, color="#E8F4FC", ec="#1B4F72", fontsize=9):
    p = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.02,rounding_size=0.15",
        facecolor=color,
        edgecolor=ec,
        linewidth=1.8,
    )
    ax.add_patch(p)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fontsize)


def arrow(ax, a, b):
    ax.annotate(
        "",
        xy=b,
        xytext=a,
        arrowprops=dict(arrowstyle="->", color="#2C3E50", lw=1.5),
    )


def main() -> None:
    # 1. System architecture
    fig, ax = plt.subplots(figsize=(12, 6.5))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 7)
    ax.axis("off")
    ax.set_title(
        "Healthcare Secure — System Architecture",
        fontsize=16,
        fontweight="bold",
        pad=12,
    )
    box(
        ax,
        0.3,
        4.5,
        2.4,
        1.8,
        "Staff Android phone\n(Capacitor + Next static)\nDoctor / Staff / Lab",
        "#D5F5E3",
        "#1E8449",
    )
    box(
        ax,
        3.5,
        4.7,
        2.2,
        1.4,
        "HTTPS / mobile data\nor clinic Wi-Fi",
        "#FCF3CF",
        "#B7950B",
    )
    box(
        ax,
        6.2,
        4.2,
        2.6,
        2.2,
        "nginx (TLS)\n→ FastAPI :8000\nAuth · History\nRx · Queue · Lab",
        "#D6EAF8",
        "#1A5276",
    )
    box(
        ax,
        9.3,
        4.5,
        2.4,
        1.8,
        "Postgres / SQLite\nClinical records\nSessions · Queue",
        "#F5EEF8",
        "#6C3483",
    )
    box(
        ax,
        6.2,
        1.5,
        2.6,
        1.8,
        "Optional AI\nWhisper (STT)\nOllama / cloud LLM",
        "#FADBD8",
        "#922B21",
    )
    box(
        ax,
        0.3,
        1.5,
        2.4,
        1.8,
        "Offline queue\n(localStorage)\nvitals / lab sync",
        "#E8F8F5",
        "#0E6655",
    )
    box(
        ax,
        3.5,
        1.5,
        2.2,
        1.8,
        "Ephemeral Rx PDFs\n24h share links\nHMAC signed",
        "#FDEBD0",
        "#AF601A",
    )
    for a, b in [
        ((2.7, 5.4), (3.5, 5.4)),
        ((5.7, 5.4), (6.2, 5.4)),
        ((8.8, 5.3), (9.3, 5.3)),
        ((7.5, 4.2), (7.5, 3.3)),
        ((2.7, 2.4), (6.2, 4.2)),
        ((7.5, 4.2), (5.7, 2.8)),
    ]:
        arrow(ax, a, b)
    save(fig, "01_system_architecture.png")

    # 2. Blind identity
    fig, ax = plt.subplots(figsize=(11, 5.5))
    ax.set_xlim(0, 11)
    ax.set_ylim(0, 5.5)
    ax.axis("off")
    ax.set_title(
        "Patient Identity — HMAC Blind IDs (What Is Stored)",
        fontsize=15,
        fontweight="bold",
        pad=10,
    )
    box(
        ax,
        0.3,
        3.2,
        3.0,
        1.6,
        "Clinic enters:\nName + 10-digit phone\nOR Clinic MRN",
        "#D5F5E3",
        "#196F3D",
    )
    box(
        ax,
        4.0,
        3.2,
        3.0,
        1.6,
        "Normalize → raw key\nmrn|C-100\nor name|9876543210",
        "#FCF3CF",
        "#9A7D0A",
    )
    box(
        ax,
        7.7,
        3.2,
        3.0,
        1.6,
        "HMAC-SHA256\n(SECRET_SALT, raw)\n→ 64-char hex",
        "#D6EAF8",
        "#1A5276",
    )
    box(
        ax,
        2.5,
        0.6,
        6.0,
        1.8,
        "Database stores ONLY blind_patient_id + encounter JSON\n"
        "(notes, vitals, Rx fields, docs as base64).\n"
        "Raw phone/name/MRN are NOT columns.\n"
        "Queue may still show display_name for waiting list UX.",
        "#F5B7B1",
        "#922B21",
        fontsize=8,
    )
    arrow(ax, (3.3, 4.0), (4.0, 4.0))
    arrow(ax, (7.0, 4.0), (7.7, 4.0))
    ax.annotate(
        "",
        xy=(5.5, 2.4),
        xytext=(9.2, 3.2),
        arrowprops=dict(
            arrowstyle="->", lw=1.6, connectionstyle="arc3,rad=0.2", color="#2C3E50"
        ),
    )
    save(fig, "02_blind_identity.png")

    # 3. Voice to Rx
    fig, ax = plt.subplots(figsize=(12, 4.2))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 4)
    ax.axis("off")
    ax.set_title(
        "Clinical Workflow — Voice → Prescription PDF",
        fontsize=15,
        fontweight="bold",
        pad=8,
    )
    steps = [
        (0.2, "1. Lock\npatient", "#D5F5E3"),
        (2.2, "2. Record\nvoice", "#D6EAF8"),
        (4.2, "3. Whisper\ntranscript", "#FCF3CF"),
        (6.2, "4. LLM\nparse Rx", "#FADBD8"),
        (8.2, "5. Doctor\nsign → PDF", "#E8DAEF"),
        (10.2, "6. Print /\nshare", "#D5F5E3"),
    ]
    for i, (x, t, c) in enumerate(steps):
        box(ax, x, 1.2, 1.7, 1.6, t, c, "#2C3E50")
        if i < len(steps) - 1:
            arrow(ax, (x + 1.7, 2.0), (x + 1.9, 2.0))
    ax.text(
        6,
        0.4,
        "Staff may enter vitals anytime after lock. Lab role: results + uploads only.",
        ha="center",
        fontsize=9,
        style="italic",
    )
    save(fig, "03_voice_to_rx.png")

    # 4. Roles
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 5)
    ax.axis("off")
    ax.set_title("Clinic Roles — Who Can Do What", fontsize=15, fontweight="bold", pad=8)
    box(
        ax,
        0.3,
        2.8,
        2.8,
        1.8,
        "DOCTOR\nUnlock · lock patient\nVoice · parse · sign Rx\nVitals · lab · queue\nFull timeline",
        "#D6EAF8",
        "#1A5276",
    )
    box(
        ax,
        3.6,
        2.8,
        2.8,
        1.8,
        "STAFF\nUnlock · lock patient\nVitals · notes\nLab values · uploads\nNo Rx sign",
        "#D5F5E3",
        "#196F3D",
    )
    box(
        ax,
        6.9,
        2.8,
        2.8,
        1.8,
        "LAB\nUnlock · lock patient\nStructured lab results\nPDF uploads only\nNo vitals / Rx",
        "#FCF3CF",
        "#9A7D0A",
    )
    ax.text(
        5,
        1.2,
        "PIN unlock → X-Doctor-Session header (durable ~7 days).\n"
        "Production: REQUIRE_CLINIC_USERS=true — no open local-doctor mode.",
        ha="center",
        fontsize=9,
    )
    save(fig, "04_roles_matrix.png")

    # 5. Cloud deploy
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.set_xlim(0, 11)
    ax.set_ylim(0, 6)
    ax.axis("off")
    ax.set_title(
        "Target Deploy — Phones Everywhere (India VPS)",
        fontsize=15,
        fontweight="bold",
        pad=8,
    )
    box(
        ax,
        0.3,
        3.5,
        2.5,
        1.8,
        "Phones on 4G\nOpen app → PIN\nNo clinic PC",
        "#D5F5E3",
        "#196F3D",
    )
    box(
        ax,
        3.5,
        3.5,
        2.5,
        1.8,
        "DNS\napi.clinic.example\nLet's Encrypt TLS",
        "#FCF3CF",
        "#9A7D0A",
    )
    box(
        ax,
        6.7,
        2.8,
        3.8,
        2.8,
        "Mumbai VPS (~Rs 400–1500/mo)\nDocker Compose:\n  nginx :443\n  FastAPI\n  Postgres\nNightly pg_dump backup",
        "#D6EAF8",
        "#1A5276",
    )
    box(
        ax,
        0.3,
        0.8,
        5.5,
        1.6,
        "Do NOT use free PaaS for live PHI\n(cold starts, DB expiry, often non-India).\n"
        "Secrets live only in server .env — never in git.",
        "#FADBD8",
        "#922B21",
        fontsize=8,
    )
    arrow(ax, (2.8, 4.4), (3.5, 4.4))
    arrow(ax, (6.0, 4.4), (6.7, 4.4))
    save(fig, "05_cloud_vps_deploy.png")

    # 6. Debug loop
    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 5.5)
    ax.axis("off")
    ax.set_title(
        "Student Debugging Loop (Root Cause Analysis)",
        fontsize=15,
        fontweight="bold",
        pad=8,
    )
    steps2 = [
        "1. Observe\nsymptom",
        "2. List\nhypotheses",
        "3. Instrument\nor reproduce",
        "4. Evidence\nconfirms one",
        "5. Minimal\nfix",
        "6. Verify\n+ lesson",
    ]
    xs = [0.3, 1.9, 3.5, 5.1, 6.7, 8.3]
    for i, (x, t) in enumerate(zip(xs, steps2)):
        box(ax, x, 2.0, 1.4, 1.8, t, "#EBF5FB", "#1A5276", fontsize=8)
        if i < 5:
            arrow(ax, (x + 1.4, 2.9), (x + 1.5, 2.9))
    ax.text(
        5,
        0.7,
        "Never guess-fix production secrets. Reproduce locally first. Prefer one change at a time.",
        ha="center",
        fontsize=9,
        style="italic",
    )
    save(fig, "06_debug_loop.png")

    # 7. Dual root
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 5)
    ax.axis("off")
    ax.set_title("Repository Layout — Dual Root", fontsize=15, fontweight="bold", pad=8)
    box(
        ax,
        0.5,
        1.0,
        4.2,
        3.2,
        "backend/\n· FastAPI app\n· SQLAlchemy models\n· Whisper / LLM services\n"
        "· PDF generator\n· .env (gitignored)\n· tests + Dockerfile",
        "#D6EAF8",
        "#1A5276",
    )
    box(
        ax,
        5.3,
        1.0,
        4.2,
        3.2,
        "frontend/\n· Next.js App Router\n· Tailwind UI\n· Capacitor Android\n"
        "· static export → out/\n· components + context\n· offline queue + i18n",
        "#D5F5E3",
        "#196F3D",
    )
    save(fig, "07_dual_root.png")

    # 8. Secrets lifecycle
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.set_xlim(0, 11)
    ax.set_ylim(0, 5)
    ax.axis("off")
    ax.set_title(
        "Secrets Lifecycle — Safe Handling (No Secrets in Git)",
        fontsize=15,
        fontweight="bold",
        pad=8,
    )
    box(ax, 0.3, 2.5, 2.4, 1.8, "Generate\nopenssl rand\nor password mgr", "#D5F5E3", "#196F3D")
    box(ax, 3.0, 2.5, 2.4, 1.8, "Store only in\nserver .env\n(gitignored)", "#D6EAF8", "#1A5276")
    box(ax, 5.7, 2.5, 2.4, 1.8, "Commit only\n.env.example\nplaceholders", "#FCF3CF", "#9A7D0A")
    box(ax, 8.4, 2.5, 2.3, 1.8, "Rotate on\nstaff leave\nor leak", "#FADBD8", "#922B21")
    for x in (2.7, 5.4, 8.1):
        arrow(ax, (x, 3.4), (x + 0.3, 3.4))
    ax.text(
        5.5,
        1.0,
        "SECRET_KEY · SECRET_SALT · CLINIC_USERS PINs · DB password · API keys\n"
        "Never paste real values into docs, chat, or commits.",
        ha="center",
        fontsize=9,
    )
    save(fig, "08_secrets_lifecycle.png")

    print("all diagrams ok →", OUT)


if __name__ == "__main__":
    main()
