import os


def test_m01_widescreen_layout():
    path = 'alphabrain_desktop/src/screens/M01_NodeSetup.tsx'
    assert os.path.exists(path)
    with open(path) as f:
        content = f.read()
    assert 'lg:grid-cols-3' in content
    assert 'Host Topology' in content
    assert 'max-w-[1800px]' in content

def test_m02_panoramic():
    path = 'alphabrain_desktop/src/screens/M02_PairingStation.tsx'
    assert os.path.exists(path)
    with open(path) as f:
        content = f.read()
    assert 'max-w-6xl' not in content
    assert 'max-w-[1800px]' in content
    assert 'panoramic-layout' in content

def test_m03_widescreen():
    path = 'alphabrain_desktop/src/screens/M03_CommandNode.tsx'
    assert os.path.exists(path)
    with open(path) as f:
        content = f.read()
    assert 'h-64' not in content
    assert 'h-[500px]' in content
    assert 'xl:grid-cols-4' in content
    assert 'max-w-[1800px]' in content

def test_m04_enclave():
    path = 'alphabrain_desktop/src/screens/M04_SecurityEnclave.tsx'
    assert os.path.exists(path)
    with open(path) as f:
        content = f.read()
    assert 'xl:grid-cols-3' in content
    assert 'max-w-[1800px]' in content

def test_app_container():
    path = 'alphabrain_desktop/src/App.tsx'
    assert os.path.exists(path)
    with open(path) as f:
        content = f.read()
    assert 'export const App: React.FC' in content
    assert 'w-72' in content
    assert 'flex-1 flex overflow-hidden' in content
