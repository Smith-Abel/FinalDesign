"""
积分业务服务层

所有积分变更逻辑统一在此处理，视图层只负责调用，
确保积分记录与用户积分字段的原子性更新。
"""
import random
from django.db import transaction
from .models import CreditDetail


# ── 积分规则常量 ──────────────────────────────────────────────
CREDIT_REGISTER_MIN = 50        # 新用户注册奖励下限
CREDIT_REGISTER_MAX = 100       # 新用户注册奖励上限
CREDIT_PROFILE_COMPLETE = 15    # 资料完善奖励（固定值，位于 10~20 范围内）
CREDIT_FIRST_HELP = 10          # 首次助人奖励
CREDIT_PUBLISH_FEE = 5          # 发布任务手续费（从发布者扣除，防止刷任务）


def award_credits(user, amount: int, reason: str) -> CreditDetail:
    """
    原子性地给用户增加（或扣减）积分，并写入明细记录。
    amount 为正表示增加，为负表示扣减。
    返回创建的 CreditDetail 对象。
    """
    with transaction.atomic():
        # 使用 select_for_update 防止并发下积分计算错误
        from .models import User
        locked_user = User.objects.select_for_update().get(pk=user.pk)
        locked_user.credit_score += amount
        locked_user.save(update_fields=['credit_score'])

        record = CreditDetail.objects.create(
            user=locked_user,
            change_amount=amount,
            reason=reason,
        )
    # 刷新调用方持有的 user 对象，避免后续使用旧的 credit_score 值
    user.refresh_from_db(fields=['credit_score'])
    return record


def grant_register_bonus(user) -> int:
    """
    新用户注册奖励：随机发放 50～100 积分。
    调用方需确保只在 created=True 时调用此函数。
    返回实际发放的积分数。
    """
    amount = random.randint(CREDIT_REGISTER_MIN, CREDIT_REGISTER_MAX)
    award_credits(user, amount, f'新用户注册奖励')
    return amount


def grant_profile_bonus(user) -> bool:
    """
    资料完善奖励：当用户首次同时填写了 student_id、avatar、college 后触发。
    使用 profile_reward_given 标志位保证只奖励一次。
    返回 True 表示本次触发了奖励，False 表示条件未满足或已奖励过。
    """
    if user.profile_reward_given:
        return False

    # 三项信息都已填写才视为"资料完善"
    if not (user.student_id and user.avatar and user.college):
        return False

    with transaction.atomic():
        from .models import User
        # 再次加锁确认标志位，防止并发请求重复发放
        locked_user = User.objects.select_for_update().get(pk=user.pk)
        if locked_user.profile_reward_given:
            return False
        locked_user.profile_reward_given = True
        locked_user.save(update_fields=['profile_reward_given'])

    award_credits(user, CREDIT_PROFILE_COMPLETE, '资料完善奖励（填写学号、头像、学院）')
    user.profile_reward_given = True
    return True


def grant_first_help_bonus(user) -> bool:
    """
    首次助人奖励：接单者第一次完成任务时触发。
    使用 first_help_rewarded 标志位保证只奖励一次。
    返回 True 表示本次触发了奖励。
    """
    if user.first_help_rewarded:
        return False

    with transaction.atomic():
        from .models import User
        locked_user = User.objects.select_for_update().get(pk=user.pk)
        if locked_user.first_help_rewarded:
            return False
        locked_user.first_help_rewarded = True
        locked_user.save(update_fields=['first_help_rewarded'])

    award_credits(user, CREDIT_FIRST_HELP, '首次助人奖励（第一次完成接单任务）')
    user.first_help_rewarded = True
    return True


def check_credits_sufficient(user, amount: int) -> bool:
    """
    检查用户积分是否足够支付 amount。
    接单前调用，amount <= 0 时直接放行（没有悬赏的任务不需要积分校验）。
    """
    if amount <= 0:
        return True
    return user.credit_score >= amount


def transfer_task_reward(task) -> bool:
    """
    任务完成时，将任务悬赏积分从发布者原子性转移到接单者。
    - reward_amount 转为整数积分
    - 若积分为 0 或无接单者则跳过转账
    - 使用双重 select_for_update 确保并发安全
    返回 True 表示发生了实际转账。
    """
    amount = int(task.reward_amount)
    if amount <= 0 or task.worker is None:
        return False

    with transaction.atomic():
        from .models import User
        # 同时锁定两个账户，按固定顺序（pk 小的先锁）防止死锁
        pks = sorted([task.publisher.pk, task.worker.pk])
        locked = {u.pk: u for u in User.objects.select_for_update().filter(pk__in=pks)}

        publisher = locked[task.publisher.pk]
        worker = locked[task.worker.pk]

        # 再次检查发布者积分（防止并发导致余额不足）
        if publisher.credit_score < amount:
            return False

        publisher.credit_score -= amount
        worker.credit_score += amount
        publisher.save(update_fields=['credit_score'])
        worker.save(update_fields=['credit_score'])

        CreditDetail.objects.create(
            user=publisher,
            change_amount=-amount,
            reason=f'任务 #{task.id}「{task.title}」悬赏支付',
        )
        CreditDetail.objects.create(
            user=worker,
            change_amount=amount,
            reason=f'任务 #{task.id}「{task.title}」完成获得悬赏',
        )

    # 刷新调用方持有的对象
    task.publisher.refresh_from_db(fields=['credit_score'])
    task.worker.refresh_from_db(fields=['credit_score'])
    return True


def deduct_publish_fee(user, task_title: str) -> bool:
    """
    发布任务时扣除固定手续费 CREDIT_PUBLISH_FEE 积分。
    调用前应先用 check_credits_sufficient 确认积分充足。
    返回 True 表示扣款成功。
    """
    award_credits(user, -CREDIT_PUBLISH_FEE, f'发布任务「{task_title}」手续费')
    return True


def refund_publish_fee(user, task_title: str) -> bool:
    """
    取消任务时退还发布手续费，让用户体验更友好。
    仅在任务处于 OPEN（还未被接单）状态时退款——已接单说明服务已消耗，不予退还。
    返回 True 表示已退款。
    """
    award_credits(user, CREDIT_PUBLISH_FEE, f'取消任务「{task_title}」退还手续费')
    return True
