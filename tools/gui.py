"""QuantBot Control Panel -- the application's face (stdlib Tkinter only).

LAW: this GUI OBSERVES and exercises GOVERNANCE only. It edits no parameter,
exposes no strategy control, and takes no trading action beyond what already
exists headlessly: running the loop / health report / backup / status drill,
and arming or disarming the killswitch file (STOP_NEW_TRADES). Every button is
a front door to a command the operator could already type; nothing here can
change what the system trades or how.

ARCHITECTURE: :class:`Controller` owns every action -- commands are CONSTRUCTED
here and executed through the installer's Runner interface, so the offline
tests assert exact argv lists without executing anything, and the Tk layer is a
thin shell. ONE action at a time: the controller's begin/finish guard means the
GUI can never launch two subprocesses concurrently (the loop stays the DB's
single writer; scheduled-task overlap is already harmless by idempotency, but
the GUI itself never races).
"""

from __future__ import annotations

import functools
import os
import threading
from pathlib import Path

from monitors import notify
from tools.installer import KILLSWITCH_FILE, Runner, RunResult, SubprocessRunner

# Action name -> module + extra args; the db path is appended where needed.
_DB_ACTIONS = {
    "status": ("monitors.status", []),
    "drill": ("monitors.status", ["--drill"]),
    "loop": ("execution.paper_loop", []),
    "health": ("monitors.health", []),
    "backup": ("tools.backup", []),
}


class Controller:
    """Every panel/button behind one testable, Runner-backed object."""

    def __init__(self, root: Path, runner: Runner | None = None) -> None:
        self._root = root
        self._runner: Runner = runner if runner is not None else SubprocessRunner()
        self._busy: str | None = None
        self._lock = threading.Lock()

    # ---------------------------------------------------------- commands

    @property
    def root(self) -> Path:
        return self._root

    def _python(self) -> str:
        return str(self._root / ".venv" / "Scripts" / "python.exe")

    def command(self, action: str) -> list[str]:
        """The exact argv an action runs -- the single source the tests pin."""
        if action == "telegram_test":
            return [self._python(), "-m", "monitors.notify", "--test"]
        module, extra = _DB_ACTIONS[action]
        db = str(self._root / "data" / "quantbot.db")
        return [self._python(), "-m", module, "--db", db, *extra]

    # ---------------------------------------------------------- busy guard

    @property
    def busy(self) -> str | None:
        return self._busy

    def begin(self, action: str) -> bool:
        """Claim the one-at-a-time slot; False if something is already running."""
        with self._lock:
            if self._busy is not None:
                return False
            self._busy = action
            return True

    def finish(self) -> None:
        with self._lock:
            self._busy = None

    def run_action(self, action: str) -> RunResult:
        """Execute an action's command via the Runner (caller holds the slot)."""
        return self._runner.run(self.command(action))

    # ---------------------------------------------------------- killswitch

    def killswitch_path(self) -> Path:
        return self._root / KILLSWITCH_FILE

    def killswitch_armed(self) -> bool:
        return self.killswitch_path().exists()

    def arm_killswitch(self) -> str:
        """Create STOP_NEW_TRADES (idempotent). Governance, not trading."""
        path = self.killswitch_path()
        if not path.exists():
            path.write_text("armed via control panel\n", encoding="utf-8")
        return f"killswitch ARMED ({path.name} present) — no NEW orders"

    def disarm_killswitch(self) -> str:
        path = self.killswitch_path()
        if path.exists():
            path.unlink()
        return f"killswitch DISARMED ({path.name} absent) — trading resumes"

    # ---------------------------------------------------------- panels

    def telegram_configured(self) -> bool:
        return notify.load_config(root=self._root) is not None

    def loop_log_tail(self, max_lines: int = 40) -> str:
        log = self._root / "data" / "loop.log"
        if not log.exists():
            return "(no data\\loop.log yet)"
        lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
        return "\n".join(lines[-max_lines:])

    def latest_health_report(self) -> str:
        health_dir = self._root / "data" / "health"
        reports = sorted(health_dir.glob("health-*.txt")) if health_dir.exists() else []
        if not reports:
            return "(no health report yet — press 'Health Report Now')"
        return reports[-1].read_text(encoding="utf-8", errors="replace")


# --------------------------------------------------------------------------- #
# The Tk shell (thin; nothing below is imported by tests).
# --------------------------------------------------------------------------- #


def _run_app(controller: Controller) -> None:  # pragma: no cover -- Tk shell
    import tkinter as tk
    from tkinter import messagebox, ttk

    app = tk.Tk()
    app.title("QuantBot Control Panel — observe + governance only")
    app.geometry("980x720")

    # ---- top: status panel + buttons ----
    top = ttk.Frame(app, padding=8)
    top.pack(fill="x")
    killswitch_var = tk.StringVar()
    status_box = tk.Text(app, height=14, state="disabled", font=("Consolas", 9))
    output_box = tk.Text(app, height=12, state="disabled", font=("Consolas", 9))

    def put(box: tk.Text, text: str) -> None:
        box.configure(state="normal")
        box.delete("1.0", "end")
        box.insert("1.0", text)
        box.configure(state="disabled")

    def append_output(text: str) -> None:
        output_box.configure(state="normal")
        output_box.insert("end", text + "\n")
        output_box.see("end")
        output_box.configure(state="disabled")

    notebook = ttk.Notebook(app)
    log_box = tk.Text(notebook, state="disabled", font=("Consolas", 9))
    health_box = tk.Text(notebook, state="disabled", font=("Consolas", 9))
    notebook.add(log_box, text="loop.log (tail)")
    notebook.add(health_box, text="latest health report")

    buttons: list[ttk.Button] = []

    def refresh_panels() -> None:
        from monitors.status import run_status

        results, overall = run_status(
            controller.root / "data" / "quantbot.db", root=controller.root
        )
        lines = [f"{r.name}: {r.status} - {r.detail}" for r in results]
        put(status_box, "\n".join([*lines, f"OVERALL: {overall}"]))
        put(log_box, controller.loop_log_tail())
        put(health_box, controller.latest_health_report())
        killswitch_var.set(
            "KILLSWITCH: ARMED — no new trades"
            if controller.killswitch_armed()
            else "killswitch: not armed"
        )

    def set_buttons_enabled(enabled: bool) -> None:
        for button in buttons:
            button.configure(state="normal" if enabled else "disabled")

    def launch(action: str, label: str) -> None:
        if not controller.begin(action):
            messagebox.showinfo(
                "Busy", f"'{controller.busy}' is still running — one at a time."
            )
            return
        set_buttons_enabled(False)
        append_output(f"── {label} started ──")

        def worker() -> None:
            try:
                result = controller.run_action(action)
                text = result.output.strip() or "(no output)"
                code = result.returncode
            except Exception as exc:  # noqa: BLE001 -- shown, never swallowed
                text, code = f"ERROR: {notify.sanitize(str(exc))}", -1
            def done() -> None:
                append_output(text)
                append_output(f"── {label} finished (exit {code}) ──")
                controller.finish()
                set_buttons_enabled(True)
                refresh_panels()
            app.after(0, done)

        threading.Thread(target=worker, daemon=True).start()

    def toggle_killswitch() -> None:
        if controller.killswitch_armed():
            if messagebox.askyesno(
                "Disarm killswitch", "Delete STOP_NEW_TRADES and resume trading?"
            ):
                append_output(controller.disarm_killswitch())
        elif messagebox.askyesno(
            "Arm killswitch",
            "Create STOP_NEW_TRADES? The loop will place NO new orders "
            "(pending fills still settle; equity still marks).",
        ):
            append_output(controller.arm_killswitch())
        refresh_panels()

    specs: list[tuple[str, str | None, str]] = [
        ("Refresh Status", None, "refresh"),
        ("Run Loop Now", "loop", "paper loop"),
        ("Health Report Now", "health", "health report"),
        ("Backup Now", "backup", "backup"),
        ("Test the Lights (drill)", "drill", "red-light drill"),
    ]
    for column, (label, action, pretty) in enumerate(specs):
        if action is None:
            button = ttk.Button(top, text=label, command=refresh_panels)
        else:
            button = ttk.Button(
                top, text=label,
                command=functools.partial(launch, action, pretty),
            )
        button.grid(row=0, column=column, padx=3)
        buttons.append(button)

    kill_button = ttk.Button(top, text="Arm/Disarm Killswitch", command=toggle_killswitch)
    kill_button.grid(row=0, column=len(specs), padx=3)
    buttons.append(kill_button)

    if controller.telegram_configured():
        telegram_button = ttk.Button(
            top, text="Send Test Telegram",
            command=lambda: launch("telegram_test", "telegram test"),
        )
        telegram_button.grid(row=0, column=len(specs) + 1, padx=3)
        buttons.append(telegram_button)

    ttk.Label(app, textvariable=killswitch_var, padding=4).pack(anchor="w")
    ttk.Label(app, text="STATUS", padding=(8, 0)).pack(anchor="w")
    status_box.pack(fill="x", padx=8)
    ttk.Label(app, text="ACTION OUTPUT", padding=(8, 0)).pack(anchor="w")
    output_box.pack(fill="x", padx=8)
    notebook.pack(fill="both", expand=True, padx=8, pady=8)

    refresh_panels()
    app.mainloop()


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    os.chdir(root)  # -m module lookups + relative data paths resolve from root
    _run_app(Controller(root))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
