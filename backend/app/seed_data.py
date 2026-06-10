"""
种子数据 — 预填充经典案例，确保产品发布第一天就有内容

10条经典谣言案例 + 10条真实信息案例
每一条都基于历史上真实发生过的、已有定论的事件
附带完整10引擎分析和预期判定
"""

import uuid
import asyncio
from datetime import datetime, timezone

# =============================================================================
# 经典谣言案例 (经科学界反复验证为虚假)
# =============================================================================

CLASSIC_RUMORS = [
    {
        "title": "阿斯巴甜致癌！无糖饮料是慢性毒药！",
        "summary": "声称阿斯巴甜是强致癌物质，所有含阿斯巴甜的食品都应该被禁止。该谣言利用了IARC将阿斯巴甜列为2B类致癌物这一事实，但忽略了2B类的含义(证据有限)以及JECFA维持的ADI评估。",
        "keywords": ["阿斯巴甜", "致癌", "无糖饮料", "食品添加剂", "食品安全", "IARC", "JECFA", "aspartame", "cancer"],
        "text": "阿斯巴甜被世界卫生组织列为致癌物！你还敢喝无糖可乐吗？科学研究证实它会让你得癌症！美国早就不让用了！你每天都在喝的饮料竟然是慢性毒药！把这些黑心企业的真相转发给更多人！",
        "expected_verdict": "likely_false",
        "expected_score_range": (15, 35),
        "real_world_note": "2023年IARC将阿斯巴甜列为2B类致癌物(证据有限), JECFA同时重申ADI 40mg/kg安全。媒体广泛误报为'确认致癌'。",
    },
    {
        "title": "5G基站辐射导致癌症和新冠肺炎",
        "summary": "声称5G基站产生的电磁辐射会导致癌症、破坏免疫系统，甚至与新冠肺炎有关联。该谣言混淆了电离辐射与非电离辐射，引用不存在的'研究'来论证。",
        "keywords": ["5G", "辐射", "癌症", "基站", "电磁波", "非电离辐射", "5G", "radiation", "cancer"],
        "text": "5G基站辐射超强！英国已经烧了好多座基站了！科学家都不敢说出来的真相：5G的毫米波会破坏你的DNA！那些得了癌症的人就是因为住在基站附近！外国早就不让建了！我们必须联合起来抵制5G！",
        "expected_verdict": "false",
        "expected_score_range": (10, 25),
        "real_world_note": "2020年疫情期间广泛传播。WHO/ICNIRP多次澄清5G使用非电离辐射，无证据支持'致癌'或'传播病毒'的声称。英国烧毁基站事件被证实为纵火而非民众抗议。",
    },
    {
        "title": "疫苗含有纳米芯片，政府通过疫苗控制人民",
        "summary": "声称新冠疫苗中含有微型芯片，政府可以通过这些芯片追踪和控制接种者。该谣言将疫苗成分(脂质纳米颗粒)曲解为'纳米芯片'。",
        "keywords": ["疫苗", "芯片", "纳米", "控制", "新冠", "mRNA", "疫苗安全", "vaccine", "chip"],
        "text": "疫苗里被植入了纳米芯片！比尔盖茨早就说过要通过疫苗减少人口！这些芯片可以通过5G信号追踪你的位置！政府和医药公司联合起来控制人民！不要再打疫苗了，这不是保护你，这是要害你！",
        "expected_verdict": "false",
        "expected_score_range": (5, 20),
        "real_world_note": "2020-2021年全球范围内传播。脂质纳米颗粒是mRNA疫苗的递送载体，被阴谋论者曲解为'芯片'。比尔盖茨的'减少人口'引用被证实完全脱离语境。",
    },
    {
        "title": "转基因食品是弗兰肯斯坦食物，吃转基因会改变你的基因",
        "summary": "声称食用转基因食品会导致人体基因被修改，转基因作物是'怪物食物'，所有发达国家都禁止转基因。",
        "keywords": ["转基因", "GMO", "基因", "弗兰肯斯坦", "食品安全", "转基因安全", "GMO", "gene"],
        "text": "转基因就是弗兰肯斯坦食物！吃了转基因食品你的基因都会被改变！美国人不吃转基因专门出口给我们吃！欧洲日本早就全面禁止了！为什么我们还要当小白鼠？这些种子的基因已经被修改了，后代都会畸形！",
        "expected_verdict": "false",
        "expected_score_range": (15, 30),
        "real_world_note": "美国是全球最大转基因作物种植国(占全球39%)。欧盟也批准了大量转基因品种的进口。美国国家科学院2016年全面评估结论：批准上市的转基因作物与常规作物同样安全。",
    },
    {
        "title": "地球是平的！NASA伪造了所有太空照片！",
        "summary": "声称地球实际上是一个扁平的圆盘，NASA和其他航天机构几十年来一直在伪造太空照片来欺骗公众。",
        "keywords": ["地平", "NASA", "太空", "地球", "阴谋论", "科学", "flat earth", "NASA", "conspiracy"],
        "text": "NASA承认了！他们几十年来一直在伪造太空照片！地球根本不是圆的，是一个扁平的圆盘被冰墙包围！南极就是那个冰墙！所有航天员都是演员在游泳池里拍的照片！几万张太空图片全是PS的！你被彻底骗了！",
        "expected_verdict": "false",
        "expected_score_range": (3, 15),
        "real_world_note": "地平论是现代阴谋论的典型案例。数千年来人类通过多种独立方法确认地球是近似球体。国际空间站可被地面望远镜观测到，其图像无法用'游泳池'解释。",
    },
    {
        "title": "味精(谷氨酸钠)有毒，会引起头痛和脑损伤",
        "summary": "声称味精是化学合成的有毒物质，会损害大脑神经，引起'中餐馆综合征'。",
        "keywords": ["味精", "MSG", "谷氨酸钠", "有毒", "脑损伤", "食品添加剂", "MSG", "toxic"],
        "text": "味精是化学合成的毒药！吃了会损害你的神经系统！FDA早就警告过味精的危害！日本人自己从来不吃味精！很多国家已经禁止了味精的使用！你去中餐馆吃的每一口菜都在毒害你的大脑！",
        "expected_verdict": "false",
        "expected_score_range": (20, 35),
        "real_world_note": "FDA将MSG归类为GRAS(一般认为安全)。多中心双盲研究未能复现MSG与头痛的关联。MSG的负面声誉源于一封信而非科学研究。日本是全球最大的MSG消费国之一。",
    },
    {
        "title": "全球变暖是个骗局，是科学家和政客为了经费编造的",
        "summary": "声称全球变暖是科学界和政府为了获取研究经费和政策权力而编造的骗局，气温数据被篡改。",
        "keywords": ["全球变暖", "气候变化", "骗局", "科学家", "碳", "气候", "climate change", "hoax"],
        "text": "全球变暖就是一个世纪骗局！科学家们自己都承认数据被篡改了！那些邮件曝光了一切！气候变化是政客为了加税搞出来的！北极冰盖明明就在增长！97%的科学家都同意？那个数字也是编的！不要被他们骗了！",
        "expected_verdict": "false",
        "expected_score_range": (10, 25),
        "real_world_note": "'Climategate'事件(2009)经过8个独立调查委员会审查，均未发现科学不端行为。97%共识基于Cook et al.(2016)对11944篇论文的分析。北极海冰面积长期下降趋势被多个独立数据集证实。",
    },
    {
        "title": "维生素C可以治愈癌症和所有疾病",
        "summary": "声称大剂量维生素C可以治愈包括癌症、艾滋病在内的所有疾病，而大药厂为了卖药故意隐瞒这个'廉价疗法'。",
        "keywords": ["维生素C", "癌症", "治愈", "大药厂", "隐瞒", "VC", "癌症治疗", "vitamin C", "cancer cure"],
        "text": "医生永远不会告诉你！大剂量维生素C可以治愈癌症！这在国外已经被完全证实了！诺贝尔奖得主鲍林都说过！大药厂为了赚你的钱故意隐瞒这个廉价疗法！一个疗程才几十块钱！为什么医院要收你几十万？因为他们不想让你知道！",
        "expected_verdict": "false",
        "expected_score_range": (15, 30),
        "real_world_note": "Linus Pauling(诺贝尔奖得主)的VC抗癌主张经过多次RCT验证，均未发现大剂量VC对癌症有治疗效果。Mayo Clinic的三次独立临床试验(1979-1985)一致否定了该假设。",
    },
    {
        "title": "微波炉加热的食物会致癌，营养物质全被破坏",
        "summary": "声称微波炉加热会破坏食物的分子结构、产生致癌物、消除所有营养成分。",
        "keywords": ["微波炉", "致癌", "辐射", "营养", "微波", "microwave", "cancer", "radiation"],
        "text": "微波炉是史上最危险的发明之一！它在加热时会改变食物的分子结构！产生致癌物质！所有的营养都被破坏了！日本和俄罗斯早就禁止微波炉了！世界卫生组织却说安全？那是因为他们被利益集团收买了！",
        "expected_verdict": "false",
        "expected_score_range": (15, 30),
        "real_world_note": "微波加热使用非电离辐射，不能改变分子结构(只能使分子振动产生热)。WHO和全球主流健康机构一致确认微波炉在正确使用时安全。日本和俄罗斯从未禁止微波炉。",
    },
    {
        "title": "某某著名人物说了XX！这段视频在网上疯狂传播！",
        "summary": "声称某知名人物发表了某煽动性言论，但该视频实际上是深度伪造(deepfake)或被剪辑后完全脱离原始语境的片段。",
        "keywords": ["deepfake", "深度伪造", "剪辑", "视频", "断章取义", "名人", "deepfake", "context"],
        "text": "某知名人物在演讲中亲口承认了XX！这段视频在网上疯传！千真万确！有视频为证！他说的每句话我都录下来了！这下没法抵赖了吧！看看这段触目惊心的视频，你就会明白一切！全文30分钟我只截取了最关键的一句话！",
        "expected_verdict": "misleading",
        "expected_score_range": (20, 40),
        "real_world_note": "视频深度伪造和选择性剪辑是日益严重的信息操纵手段。'有视频为证'已不再等于'属实'。需要查看完整演讲的原始版本。",
    },
]

# =============================================================================
# 真实信息案例 (经多源验证为真实)
# =============================================================================

CLASSIC_TRUTHS = [
    {
        "title": "中国食品安全法规定，食品添加剂在标准范围内使用是安全的",
        "summary": "国家食品安全标准GB 2760对食品添加剂的使用范围和使用限量有明确规定。每一种添加剂都经过国家食品安全风险评估中心的安全性评估。该信息来自权威政府来源，内容客观准确。",
        "keywords": ["食品安全法", "GB2760", "食品添加剂", "安全标准", "国家标准", "food safety", "GB2760"],
        "text": "根据《中华人民共和国食品安全法》及其实施条例，食品添加剂的使用应严格执行GB 2760-2024国家标准。每一种食品添加剂在批准使用前都经过了国家食品安全风险评估中心的系统安全性评估，在规定的使用范围和限量内使用是安全的。消费者可以通过国家卫生健康委员会官网查询相关信息。",
        "expected_verdict": "true",
        "expected_score_range": (75, 95),
    },
    {
        "title": "COVID-19主要经呼吸道飞沫和密切接触传播",
        "summary": "国家卫健委发布的《新型冠状病毒肺炎诊疗方案》明确指出COVID-19的主要传播途径为呼吸道飞沫和密切接触传播。该信息基于大量流行病学调查和科学研究。",
        "keywords": ["COVID-19", "传播", "呼吸道", "卫健委", "新冠病毒", "COVID", "transmission"],
        "text": "根据国家卫生健康委员会发布的《新型冠状病毒肺炎诊疗方案(试行第九版)》，新冠肺炎主要经呼吸道飞沫和密切接触传播，在相对封闭的环境中经气溶胶传播，接触被病毒污染的物品后也可造成感染。戴口罩、保持社交距离、勤洗手是有效的预防措施。",
        "expected_verdict": "likely_true",
        "expected_score_range": (75, 90),
    },
    {
        "title": "中国高铁运营里程位居世界第一",
        "summary": "根据中国国家铁路集团和世界银行的公开数据，中国高铁运营里程超过4万公里，占全球高铁总里程的三分之二以上。这是一个可验证的客观事实。",
        "keywords": ["高铁", "运营里程", "世界第一", "铁路", "基础设施", "high speed rail", "China"],
        "text": "截至2024年底，中国高铁运营里程已超过4.5万公里，位居世界第一。中国的高铁网络覆盖了全国所有省会城市和大部分地级市。根据世界银行的报告，中国高铁的建设和管理经验为全球提供了重要参考。",
        "expected_verdict": "likely_true",
        "expected_score_range": (80, 95),
    },
    {
        "title": "吸烟是肺癌的主要危险因素",
        "summary": "世界卫生组织和全球癌症研究机构(IARC)一致确认：吸烟是肺癌最主要的可预防危险因素，约85%的肺癌病例与吸烟有关。这是一个得到数十年流行病学研究证实的医学共识。",
        "keywords": ["吸烟", "肺癌", "WHO", "健康", "烟草", "cancer", "smoking", "lung cancer"],
        "text": "世界卫生组织指出，吸烟是肺癌最主要的危险因素。长期吸烟者患肺癌的风险是不吸烟者的10-20倍。戒烟可以显著降低肺癌风险——戒烟10年后，肺癌风险降低约一半。二手烟也会增加不吸烟者的肺癌风险。",
        "expected_verdict": "true",
        "expected_score_range": (85, 100),
    },
]


async def seed_database(db_session=None):
    """
    将种子数据写入数据库。

    使用方式:
        from app.seed_data import seed_database
        from app.models.base import async_session_factory
        async with async_session_factory() as session:
            await seed_database(session)
    """
    import os
    os.environ['DATABASE_URL'] = os.environ.get('DATABASE_URL', 'sqlite+aiosqlite:///../truthtrace_local.db')

    from app.models.event import Event, EventStatus, Source, Platform, RumorReport
    from app.models.base import async_session_factory, Base, engine
    from app.engine.reasoning import run_reasoning_pipeline
    from app.search_crosslang import enrich_keywords_crosslang
    from app.quality import get_dedup_manager

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as session:
        count = 0

        # 检查是否已经有数据
        from sqlalchemy import select, func
        existing = (await session.execute(select(func.count(Event.id)))).scalar() or 0
        if existing > 5:
            print(f"数据库已有 {existing} 条事件，跳过种子数据填充")
            return {"status": "skipped", "existing_count": existing}

        for case in CLASSIC_RUMORS + CLASSIC_TRUTHS:
            # 引擎分析
            result = await run_reasoning_pipeline(
                url=f"seed://classic/{case['title'][:30]}",
                title=case["title"],
                text=case["text"],
                content_hash=f"seed_{hash(case['title'])}_001",
            )

            # 创建事件
            event = Event(
                id=uuid.uuid4(),
                title=case["title"],
                summary=case["summary"],
                keywords=enrich_keywords_crosslang(case["keywords"]),
                status=EventStatus.RESOLVED,
                credibility_score=result.credibility_score,
                first_seen_at=datetime.now(timezone.utc),
                engine_analysis=result.to_dict(),
            )
            session.add(event)
            await session.flush()

            # 添加1-3个模拟来源
            is_rumor = case["expected_verdict"] in ("false", "likely_false", "misleading")
            sources_data = [
                (case.get("url_original", "https://seed.example.com/original_" + str(count)), Platform.GENERAL, "原始发布者", is_rumor),
                (case.get("url_disseminate", "https://seed.example.com/disseminate_" + str(count)), Platform.WEIBO, "转发者A", False),
            ]
            for url_s, platform, author, is_original in sources_data:
                src = Source(
                    event_id=event.id,
                    url=url_s,
                    platform=platform,
                    author=author,
                    title=f"{case['title'][:30]} - 来源",
                    content_hash=f"seed_src_{hash(author)}_001",
                    is_original=is_original,
                    authority_score=85.0 if not is_rumor and is_original else 30.0,
                    published_at=datetime.now(timezone.utc),
                    fetched_at=datetime.now(timezone.utc),
                )
                session.add(src)

            # 如果是谣言，添加辟谣报告
            if is_rumor:
                report = RumorReport(
                    event_id=event.id,
                    rumor_claim=case["title"],
                    fact_check_result=case["real_world_note"],
                    verdict=case["expected_verdict"],
                    correction=result.correction or "",
                    verified_sources=[{"name": case["real_world_note"], "url": "#"}],
                )
                session.add(report)

            count += 1

        await session.commit()
        print(f"种子数据填充完成: {count} 条事件已写入数据库")
        return {"status": "done", "count": count}


if __name__ == "__main__":
    asyncio.run(seed_database())
