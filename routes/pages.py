"""Page routes that render Jinja2 templates."""

from __future__ import annotations

from flask import Blueprint, redirect, render_template, url_for

page_bp = Blueprint("pages", __name__)


@page_bp.get("/")
def index():
    return redirect(url_for("pages.library"))


@page_bp.get("/library")
def library():
    return render_template("library.html")
