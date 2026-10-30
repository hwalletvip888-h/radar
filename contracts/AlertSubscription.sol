// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title 海豚Radar 订阅合约（AlertSubscription）
/// @notice TapeOut 生态安全警报的付费订阅基础设施。
///         三个套餐（Free / Pro / Enterprise），统一走「连钱包 → subscribe → 上链」。
///         免费只付 gas，Pro/Enterprise 用 X Layer 桥接 BEM 付费。
///         链上订阅记录 = 平台用户量凭证（每个订阅者都有可验证的链上记录）。
/// @dev 部署在 X Layer（chainId 196）。BEM 8 位小数。
interface IERC20 {
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
    function transfer(address to, uint256 amount) external returns (bool);
}

/// @notice 简版 Ownable（单 owner，可转移、可弃权）
abstract contract Ownable {
    address public owner;
    event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);

    error OwnableUnauthorizedAccount(address account);
    error OwnableInvalidOwner(address account);

    constructor() {
        owner = msg.sender;
        emit OwnershipTransferred(address(0), msg.sender);
    }

    modifier onlyOwner() {
        if (msg.sender != owner) revert OwnableUnauthorizedAccount(msg.sender);
        _;
    }

    function transferOwnership(address newOwner) external onlyOwner {
        if (newOwner == address(0)) revert OwnableInvalidOwner(address(0));
        emit OwnershipTransferred(owner, newOwner);
        owner = newOwner;
    }

    function renounceOwnership() external onlyOwner {
        emit OwnershipTransferred(owner, address(0));
        owner = address(0);
    }
}

/// @notice 简版 ReentrancyGuard
abstract contract ReentrancyGuard {
    uint256 private constant NOT_ENTERED = 1;
    uint256 private constant ENTERED = 2;
    uint256 private _status = NOT_ENTERED;

    error ReentrancyGuardReentrantCall();

    modifier nonReentrant() {
        if (_status == ENTERED) revert ReentrancyGuardReentrantCall();
        _status = ENTERED;
        _;
        _status = NOT_ENTERED;
    }
}

contract AlertSubscription is Ownable, ReentrancyGuard {
    /// @notice 套餐等级
    enum Tier { FREE, PRO, ENTERPRISE }

    /// @notice 推送渠道位图（bytes32 低 4 位）
    bytes32 public constant CH_TELEGRAM = bytes32(uint256(1) << 0);
    bytes32 public constant CH_WEBHOOK  = bytes32(uint256(1) << 1);
    bytes32 public constant CH_TAPESEND = bytes32(uint256(1) << 2);
    bytes32 public constant CH_EMAIL    = bytes32(uint256(1) << 3);

    /// @notice 单次订阅最长月数（120 个月 = 10 年）
    uint256 public constant MAX_MONTHS = 120;

    IERC20 public immutable bem;   ///< X Layer 桥接 BEM（0x60e6…3952）
    bool public paused;            ///< 紧急暂停开关

    /// @notice 每套餐每月价格（BEM，8 位小数）。FREE=0，PRO=0.2 BEM，ENTERPRISE 由 owner 定制
    mapping(Tier => uint256) public monthlyPrice;

    /// @notice 订阅详情
    struct Subscription {
        uint256 expiry;     ///< 到期时间戳（秒）
        Tier    tier;       ///< 套餐等级
        bytes32 channels;   ///< 渠道位图
        string  contact;    ///< 联系方式：telegram chat_id / webhook URL / 容器地址
        uint256 paid;       ///< 已付 BEM（用于取消退款，8 位小数）
    }

    mapping(address => Subscription) public subscriptions;

    /// @notice 平台累计收入（BEM，8 位小数）
    uint256 public totalRevenue;

    // ── 事件 ──────────────────────────────────────────────
    event Subscribed(address indexed user, uint256 months, Tier tier, uint256 expiry, bytes32 channels, string contact, uint256 paid);
    event Upgraded(address indexed user, Tier from, Tier to, uint256 extraPaid);
    event ContactUpdated(address indexed user, bytes32 channels, string contact);
    event Cancelled(address indexed user, uint256 refunded);
    event PriceSet(Tier tier, uint256 monthlyPrice);
    event Withdrawn(address indexed to, uint256 amount);
    event Paused(bool paused);

    // ── 错误 ──────────────────────────────────────────────
    error InvalidMonths(uint256 months);
    error NoChannel();
    error ZeroAmount();
    error NotActive();
    error ContractPaused();
    error InvalidTier();

    constructor(address bem_) {
        bem = IERC20(bem_);
        monthlyPrice[Tier.FREE] = 0;
        monthlyPrice[Tier.PRO] = 20_000_000;   // 0.2 BEM
        // ENTERPRISE 由 owner 用 setPrice 设定
    }

    modifier whenNotPaused() {
        if (paused) revert ContractPaused();
        _;
    }

    /// @notice 订阅（或续费）。先 approve 本合约扣 BEM（免费套餐不需要，只付 gas）。
    /// @param months 订阅月数（1..120）
    /// @param tier 套餐等级
    /// @param channels 渠道位图
    /// @param contact 联系方式
    function subscribe(uint256 months, Tier tier, bytes32 channels, string calldata contact)
        external
        nonReentrant
        whenNotPaused
    {
        if (months < 1 || months > MAX_MONTHS) revert InvalidMonths(months);
        if (channels == bytes32(0)) revert NoChannel();

        uint256 price = monthlyPrice[tier] * months;
        if (price > 0) {
            if (!bem.transferFrom(msg.sender, address(this), price)) revert ZeroAmount();
            totalRevenue += price;
        }

        Subscription storage s = subscriptions[msg.sender];
        // 续费：从当前到期时间顺延；已过期的从现在起算
        uint256 base = s.expiry > block.timestamp ? s.expiry : block.timestamp;
        s.expiry = base + months * 30 days;
        s.tier = tier;
        s.channels = channels;
        s.contact = contact;
        s.paid += price;

        emit Subscribed(msg.sender, months, tier, s.expiry, channels, contact, price);
    }

    /// @notice 升级套餐（补差价）。只升不降，按剩余时间比例补差价。
    function upgrade(Tier newTier) external nonReentrant whenNotPaused {
        Subscription storage s = subscriptions[msg.sender];
        if (s.expiry <= block.timestamp) revert NotActive();
        if (uint8(newTier) <= uint8(s.tier)) revert InvalidTier();

        uint256 remainingMonths = (s.expiry - block.timestamp + 30 days - 1) / 30 days;
        uint256 oldPrice = monthlyPrice[s.tier];
        uint256 newPrice = monthlyPrice[newTier];
        uint256 extra = (newPrice - oldPrice) * remainingMonths;
        if (extra > 0) {
            if (!bem.transferFrom(msg.sender, address(this), extra)) revert ZeroAmount();
            totalRevenue += extra;
            s.paid += extra;
        }
        s.tier = newTier;
        emit Upgraded(msg.sender, s.tier, newTier, extra);
    }

    /// @notice 更新推送渠道/联系方式（不改变套餐和到期时间）
    function updateContact(bytes32 channels, string calldata contact) external whenNotPaused {
        if (channels == bytes32(0)) revert NoChannel();
        Subscription storage s = subscriptions[msg.sender];
        s.channels = channels;
        s.contact = contact;
        emit ContactUpdated(msg.sender, channels, contact);
    }

    /// @notice 取消订阅，按未消耗的整月数退还 BEM（封顶为已付金额）
    function cancel() external nonReentrant {
        Subscription storage s = subscriptions[msg.sender];
        if (s.expiry <= block.timestamp) revert NotActive();

        uint256 remainingMonths = (s.expiry - block.timestamp + 30 days - 1) / 30 days;
        uint256 monthly = monthlyPrice[s.tier];
        uint256 refund = monthly * remainingMonths;
        if (refund > s.paid) refund = s.paid;   // 退款不超过已付

        s.expiry = 0;
        s.paid = 0;
        if (refund > 0) {
            bem.transfer(msg.sender, refund);
            totalRevenue -= refund;
        }
        emit Cancelled(msg.sender, refund);
    }

    /// @notice 是否有效订阅中（不区分套餐）
    function isActive(address user) public view returns (bool) {
        return subscriptions[user].expiry > block.timestamp;
    }

    /// @notice 查询订阅详情
    function getSubscription(address user)
        external
        view
        returns (uint256 expiry, Tier tier, bytes32 channels, string memory contact, uint256 paid)
    {
        Subscription storage s = subscriptions[user];
        return (s.expiry, s.tier, s.channels, s.contact, s.paid);
    }

    /// @notice 批量查询订阅到期（供推送引擎读订阅表）
    function activeExpiry(address[] calldata users) external view returns (uint256[] memory) {
        uint256[] memory out = new uint256[](users.length);
        for (uint256 i = 0; i < users.length; i++) {
            uint256 e = subscriptions[users[i]].expiry;
            out[i] = e > block.timestamp ? e : 0;
        }
        return out;
    }

    // ── 管理员 ──────────────────────────────────────────

    /// @notice 设置套餐月价（BEM，8 位小数）
    function setPrice(Tier tier, uint256 price) external onlyOwner {
        monthlyPrice[tier] = price;
        emit PriceSet(tier, price);
    }

    /// @notice 紧急暂停/恢复订阅（暂停后不能新订阅/升级）
    function setPaused(bool p) external onlyOwner {
        paused = p;
        emit Paused(p);
    }

    /// @notice 提取平台收入（BEM）
    function withdraw(address to, uint256 amount) external onlyOwner {
        if (amount == 0) revert ZeroAmount();
        bem.transfer(to, amount);
        emit Withdrawn(to, amount);
    }
}
