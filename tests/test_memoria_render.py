from core.recursos_execucao import recommended_profile


def test_free_512mb_usa_lote_unitario():
    profile = recommended_profile(cpu_count=1, memory_limit_mb=512)
    assert profile.batch_size == 1
    assert profile.rreo_workers == 1
    assert profile.fnde_workers == 1
    assert profile.gemini_concurrency == 1


def test_standard_2gb_1cpu_continua_conservador():
    profile = recommended_profile(cpu_count=1, memory_limit_mb=2048)
    assert profile.batch_size == 2
    assert profile.rreo_workers == 1


def test_4cpu_8gb_mantem_desempenho_controlado():
    profile = recommended_profile(cpu_count=4, memory_limit_mb=8192)
    assert profile.batch_size == 8
    assert profile.rreo_workers == 3
    assert profile.fnde_workers == 2
