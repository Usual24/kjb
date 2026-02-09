from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from ..extensions import db
from ..models import (
    User,
    Channel,
    Message,
    Notification,
    KCLog,
    ShopItem,
    ShopRequest,
    Follow,
)
from ..utils import (
    login_required,
    admin_required,
    set_login,
    logout_user,
    get_current_user,
    notify,
    adjust_kc,
    to_kst,
)
from ..sockets import online_users

bp = Blueprint("views", __name__)


@bp.before_app_request
def load_user():
    get_current_user()


@bp.route("/")
def index():
    if get_current_user():
        channel = Channel.query.order_by(Channel.name.asc()).first()
        if channel:
            return redirect(url_for("views.chat", id=channel.slug))
    return render_template("index.html")


@bp.route("/signin", methods=["GET", "POST"])
def signin():
    if request.method == "POST":
        email = request.form.get("email", "").lower().strip()
        password = request.form.get("password", "")
        remember = request.form.get("remember") == "on"
        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            flash("이메일 또는 비밀번호가 올바르지 않습니다.")
            return redirect(url_for("views.signin"))
        set_login(user, remember)
        return redirect(url_for("views.chat"))
    return render_template("signin.html")


@bp.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form.get("email", "").lower().strip()
        name = request.form.get("name", "").strip()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        password_confirm = request.form.get("password_confirm", "")
        if not all([email, name, username, password]):
            flash("모든 필드를 입력해주세요.")
            return redirect(url_for("views.signup"))
        if password != password_confirm:
            flash("비밀번호가 일치하지 않습니다.")
            return redirect(url_for("views.signup"))
        email_prefix = email.split("@")[0]
        if User.query.filter(
            (User.email == email)
            | (User.username == username)
            | (User.email_prefix == email_prefix)
        ).first():
            flash("이미 등록된 계정 정보입니다.")
            return redirect(url_for("views.signup"))
        is_first = User.query.count() == 0
        user = User(
            email=email,
            email_prefix=email_prefix,
            name=name,
            username=username,
            is_admin=is_first,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        set_login(user, True)
        return redirect(url_for("views.chat"))
    return render_template("signup.html")


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("views.index"))


@bp.route("/chat")
@login_required
def chat():
    channel_slug = request.args.get("id")
    if not channel_slug:
        first_channel = Channel.query.order_by(Channel.name.asc()).first()
        if first_channel:
            return redirect(url_for("views.chat", id=first_channel.slug))
    channel = Channel.query.filter_by(slug=channel_slug).first()
    if not channel:
        flash("채널을 찾을 수 없습니다.")
        return redirect(url_for("views.index"))
    messages = (
        Message.query.filter_by(channel_id=channel.id)
        .order_by(Message.created_at.asc())
        .limit(200)
        .all()
    )
    return render_template("chat.html", channel=channel, messages=messages)


@bp.route("/profile")
@login_required
def profile():
    prefix = request.args.get("usr", "")
    user = User.query.filter_by(email_prefix=prefix).first()
    if not user:
        flash("사용자를 찾을 수 없습니다.")
        return redirect(url_for("views.index"))
    current = get_current_user()
    is_following = False
    if current:
        is_following = (
            Follow.query.filter_by(follower_id=current.id, followed_id=user.id).first()
            is not None
        )
    follower_count = Follow.query.filter_by(followed_id=user.id).count()
    following_count = Follow.query.filter_by(follower_id=user.id).count()
    return render_template(
        "profile.html",
        profile_user=user,
        is_following=is_following,
        follower_count=follower_count,
        following_count=following_count,
    )


@bp.route("/follow/<prefix>", methods=["POST"])
@login_required
def follow(prefix):
    target = User.query.filter_by(email_prefix=prefix).first_or_404()
    current = get_current_user()
    if current.id == target.id:
        return redirect(url_for("views.profile", usr=prefix))
    existing = Follow.query.filter_by(
        follower_id=current.id, followed_id=target.id
    ).first()
    if existing:
        db.session.delete(existing)
        adjust_kc(target, -50, "팔로워 감소", db, KCLog, Notification)
        notify(target.id, "팔로우", f"{current.name}님이 언팔로우했습니다.", db, Notification)
    else:
        db.session.add(Follow(follower_id=current.id, followed_id=target.id))
        adjust_kc(target, 50, "팔로워 증가", db, KCLog, Notification)
        notify(target.id, "팔로우", f"{current.name}님이 팔로우했습니다.", db, Notification)
    db.session.commit()
    return redirect(url_for("views.profile", usr=prefix))


@bp.route("/mypage", methods=["GET", "POST"])
@login_required
def mypage():
    current = get_current_user()
    if request.method == "POST":
        current.name = request.form.get("name", current.name).strip()
        current.bio = request.form.get("bio", current.bio).strip()
        current.avatar_url = request.form.get("avatar_url", current.avatar_url).strip()
        db.session.commit()
        flash("프로필이 업데이트되었습니다.")
        return redirect(url_for("views.mypage"))
    return render_template("mypage.html", profile_user=current)


@bp.route("/shop", methods=["GET", "POST"])
@login_required
def shop():
    current = get_current_user()
    items = ShopItem.query.order_by(ShopItem.priority.desc(), ShopItem.name.asc()).all()
    if request.method == "POST":
        item_id = request.form.get("item_id")
        item = ShopItem.query.get(item_id)
        if not item:
            flash("상품을 찾을 수 없습니다.")
            return redirect(url_for("views.shop"))
        if item.quantity is not None and item.quantity <= 0:
            flash("품절된 상품입니다.")
            return redirect(url_for("views.shop"))
        request_entry = ShopRequest(user_id=current.id, item_id=item.id)
        db.session.add(request_entry)
        notify(current.id, "상점", f"{item.name} 구매 요청을 접수했습니다.", db, Notification)
        db.session.commit()
        flash("구매 요청이 접수되었습니다.")
        return redirect(url_for("views.shop"))
    return render_template("shop.html", items=items)


@bp.route("/sendkc", methods=["GET", "POST"])
@login_required
def sendkc():
    current = get_current_user()
    if request.method == "POST":
        recipient_prefix = request.form.get("recipient", "").strip()
        amount = int(request.form.get("amount", "0") or 0)
        if amount <= 0:
            flash("올바른 KC를 입력해주세요.")
            return redirect(url_for("views.sendkc"))
        if current.kc_points < amount:
            flash("KC가 부족합니다.")
            return redirect(url_for("views.sendkc"))
        recipient = User.query.filter_by(email_prefix=recipient_prefix).first()
        if not recipient:
            notify(current.id, "송금", "수신자를 찾지 못해 송금이 취소되었습니다.", db, Notification)
            flash("수신자를 찾을 수 없습니다. 송금이 취소됩니다.")
            db.session.commit()
            return redirect(url_for("views.sendkc"))
        adjust_kc(current, -amount, "KC 송금", db, KCLog, Notification)
        adjust_kc(recipient, amount, "KC 수신", db, KCLog, Notification)
        notify(recipient.id, "송금", f"{current.name}님에게서 {amount} KC를 받았습니다.", db, Notification)
        db.session.commit()
        flash("송금이 완료되었습니다.")
        return redirect(url_for("views.sendkc"))
    return render_template("sendkc.html")


@bp.route("/mailbox")
@login_required
def mailbox():
    current = get_current_user()
    notifications = (
        Notification.query.filter_by(user_id=current.id)
        .order_by(Notification.created_at.desc())
        .all()
    )
    return render_template("mailbox.html", notifications=notifications)


@bp.route("/admin", methods=["GET", "POST"])
@admin_required
def admin():
    current = get_current_user()
    if request.method == "POST":
        action = request.form.get("action")
        if action == "kc_adjust":
            target_prefix = request.form.get("target")
            delta = int(request.form.get("delta", "0") or 0)
            target = User.query.filter_by(email_prefix=target_prefix).first()
            if target and delta != 0:
                adjust_kc(target, delta, "관리자 조정", db, KCLog, Notification)
                db.session.commit()
                flash("KC가 조정되었습니다.")
        elif action == "shop_decision":
            request_id = request.form.get("request_id")
            decision = request.form.get("decision")
            shop_request = ShopRequest.query.get(request_id)
            if shop_request and shop_request.status == "pending":
                if decision == "approve":
                    item = shop_request.item
                    if shop_request.user.kc_points >= item.kc_cost:
                        adjust_kc(shop_request.user, -item.kc_cost, "상점 구매", db, KCLog, Notification)
                        shop_request.status = "approved"
                        shop_request.processed_at = datetime.utcnow()
                        if item.quantity is not None:
                            item.quantity = max(0, item.quantity - 1)
                        notify(
                            shop_request.user.id,
                            "상점",
                            f"{item.name} 구매가 승인되었습니다.",
                            db,
                            Notification,
                        )
                    else:
                        shop_request.status = "denied"
                        notify(
                            shop_request.user.id,
                            "상점",
                            f"KC 부족으로 {item.name} 구매가 거절되었습니다.",
                            db,
                            Notification,
                        )
                else:
                    shop_request.status = "denied"
                    notify(
                        shop_request.user.id,
                        "상점",
                        f"{shop_request.item.name} 구매가 거절되었습니다.",
                        db,
                        Notification,
                    )
                db.session.commit()
        elif action == "channel_create":
            slug = request.form.get("slug", "").strip()
            name = request.form.get("name", "").strip()
            description = request.form.get("description", "").strip()
            if slug and name and not Channel.query.filter_by(slug=slug).first():
                db.session.add(Channel(slug=slug, name=name, description=description))
                db.session.commit()
        elif action == "channel_delete":
            channel_id = request.form.get("channel_id")
            channel = Channel.query.get(channel_id)
            if channel:
                Message.query.filter_by(channel_id=channel.id).delete()
                db.session.delete(channel)
                db.session.commit()
        elif action == "shop_item_create":
            name = request.form.get("name", "").strip()
            kc_cost = int(request.form.get("kc_cost", "0") or 0)
            description = request.form.get("description", "").strip()
            image_url = request.form.get("image_url", "").strip() or "/static/images/shop-default.svg"
            quantity = request.form.get("quantity")
            priority = int(request.form.get("priority", "0") or 0)
            quantity_value = int(quantity) if quantity else None
            if name and kc_cost > 0:
                db.session.add(
                    ShopItem(
                        name=name,
                        description=description,
                        kc_cost=kc_cost,
                        quantity=quantity_value,
                        priority=priority,
                        image_url=image_url,
                    )
                )
                db.session.commit()
        elif action == "shop_item_delete":
            item_id = request.form.get("item_id")
            item = ShopItem.query.get(item_id)
            if item:
                db.session.delete(item)
                db.session.commit()
        elif action == "user_delete":
            prefix = request.form.get("target")
            target = User.query.filter_by(email_prefix=prefix).first()
            if target and target.id != current.id:
                Message.query.filter_by(user_id=target.id).delete()
                Follow.query.filter_by(follower_id=target.id).delete()
                Follow.query.filter_by(followed_id=target.id).delete()
                Notification.query.filter_by(user_id=target.id).delete()
                KCLog.query.filter_by(user_id=target.id).delete()
                db.session.delete(target)
                db.session.commit()
    stats = {
        "user_count": User.query.count(),
        "channel_count": Channel.query.count(),
        "online_count": len(online_users),
    }
    shop_requests = (
        ShopRequest.query.filter_by(status="pending")
        .order_by(ShopRequest.created_at.desc())
        .all()
    )
    items = ShopItem.query.order_by(ShopItem.priority.desc(), ShopItem.name.asc()).all()
    channels = Channel.query.order_by(Channel.name.asc()).all()
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template(
        "admin.html",
        stats=stats,
        shop_requests=shop_requests,
        items=items,
        channels=channels,
        users=users,
    )


@bp.app_template_filter("datetime")
def format_datetime(value):
    if not value:
        return ""
    return to_kst(value).strftime("%Y-%m-%d %H:%M")
