import platform, subprocess, os, shutil

OWU_API_KEY = "sk-foxwks-bd6dc62fd0caca045e5fa615680866d4"
OWU_BASE = "http://192.168.88.202:8080"
GODZILLA_URL = "http://localhost:8085/v1/chat/completions"
TURBOQUANT_URL = "http://fox-server.lan:8082/v1/chat/completions"
TURBOQUANT_MODEL = "Qwen3.6-35B-A3B-UD-Q4_K_M.gguf"

class Tools:

    def _check_path(self, path):
        resolved = os.path.normpath(os.path.abspath(path))
        if not resolved.upper().startswith("D:\\"):
            return None, f"Acesso negado: workspace e D:\\ (tentativa: {resolved})"
        return resolved, None

    def _ps(self, cmd, timeout=10):
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd],
            capture_output=True, text=True, timeout=timeout
        )
        return r.stdout.strip() or r.stderr.strip()

    def _ssh(self, command, timeout=15):
        import paramiko
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect("192.168.88.200", username="conrado",
                           key_filename="C:/ProgramData/open-webui-ssh/id_rsa", timeout=10)
            _, stdout, stderr = client.exec_command(command, timeout=timeout)
            out = stdout.read().decode("utf-8", errors="replace").strip()
            err = stderr.read().decode("utf-8", errors="replace").strip()
            return out or err or "(sem output)"
        finally:
            client.close()

    def _win_os_name(self):
        ver = platform.version()
        try:
            build = int(ver.split(".")[2])
            if build >= 22000:
                return f"Windows 11 (build {build})"
        except Exception:
            pass
        return f"Windows {platform.release()} ({ver})"

    def get_system_info(self):
        "Retorna OS, CPU e RAM do fox-wks."
        try:
            ram_out = self._ps(
                "$os = Get-CimInstance Win32_OperatingSystem; "
                "Write-Output ($os.TotalVisibleMemorySize.ToString() + ' ' + $os.FreePhysicalMemory.ToString())"
            )
            parts = ram_out.split()
            total = int(parts[0]) // 1024 if parts else 0
            free  = int(parts[1]) // 1024 if len(parts) > 1 else 0
            return (f"OS: {self._win_os_name()}\nMaquina: {platform.node()}\nCPU: {platform.processor()}\n"
                    f"RAM: {total - free}/{total} MB usados ({free} MB livres)")
        except Exception as e:
            return f"Erro: {e}"

    def get_gpu_info(self):
        "Retorna temperatura, uso e VRAM da GPU NVIDIA do fox-wks."
        try:
            r = subprocess.run(
                ["nvidia-smi",
                 "--query-gpu=name,temperature.gpu,utilization.gpu,memory.used,memory.total,power.draw",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=10
            )
            if r.returncode != 0:
                return "nvidia-smi nao disponivel."
            out = []
            for i, line in enumerate(r.stdout.strip().splitlines()):
                p = [x.strip() for x in line.split(",")]
                if len(p) >= 6:
                    out.append(f"GPU {i}: {p[0]} | {p[1]}C | {p[2]}% | {p[3]}/{p[4]} MB VRAM | {p[5]}W")
            return "\n".join(out) or "Nenhuma GPU."
        except Exception as e:
            return f"Erro: {e}"

    def list_directory(self, path="D:\\"):
        "Lista arquivos e pastas em D:\\ ou subdiretório."
        resolved, err = self._check_path(path)
        if err: return err
        try:
            if not os.path.exists(resolved):
                return f"Diretorio nao existe: {resolved}"
            items = []
            for name in sorted(os.listdir(resolved)):
                full = os.path.join(resolved, name)
                if os.path.isdir(full):
                    items.append(f"[DIR]  {name}/")
                else:
                    items.append(f"[FILE] {name} ({os.path.getsize(full)} bytes)")
            return f"{resolved}\n" + ("\n".join(items) if items else "(vazio)")
        except Exception as e:
            return f"Erro: {e}"

    def create_directory(self, path):
        "Cria um diretório (e subdiretórios) em D:\\."
        resolved, err = self._check_path(path)
        if err: return err
        try:
            os.makedirs(resolved, exist_ok=True)
            return f"Diretorio criado: {resolved}"
        except Exception as e:
            return f"Erro: {e}"

    def write_file(self, path, content):
        "Grava qualquer arquivo de texto em D:\\ (html, txt, md, json, py, js, css...)."
        resolved, err = self._check_path(path)
        if err: return err
        try:
            os.makedirs(os.path.dirname(resolved), exist_ok=True)
            with open(resolved, "w", encoding="utf-8") as f:
                f.write(content)
            return f"Arquivo gravado: {resolved} ({len(content)} chars)"
        except Exception as e:
            return f"Erro: {e}"

    def read_file(self, path):
        "Le o conteudo de um arquivo em D:\\."
        resolved, err = self._check_path(path)
        if err: return err
        try:
            if not os.path.exists(resolved):
                return f"Nao encontrado: {resolved}"
            with open(resolved, "r", encoding="utf-8", errors="replace") as f:
                return f.read(8000)
        except Exception as e:
            return f"Erro: {e}"

    def delete_file(self, path):
        "Deleta um arquivo em D:\\."
        resolved, err = self._check_path(path)
        if err: return err
        try:
            if not os.path.exists(resolved):
                return f"Nao encontrado: {resolved}"
            if os.path.isdir(resolved):
                return "E um diretorio, use delete_directory."
            os.remove(resolved)
            return f"Deletado: {resolved}"
        except Exception as e:
            return f"Erro: {e}"

    def delete_directory(self, path):
        "Deleta um diretorio e todo seu conteudo em D:\\. Irreversivel."
        resolved, err = self._check_path(path)
        if err: return err
        if resolved.upper().rstrip("\\") == "D:":
            return "Nao e permitido deletar a raiz D:\\."
        try:
            if not os.path.exists(resolved):
                return f"Nao encontrado: {resolved}"
            shutil.rmtree(resolved)
            return f"Diretorio removido: {resolved}"
        except Exception as e:
            return f"Erro: {e}"

    def run_powershell(self, command):
        "Executa PowerShell read-only no fox-wks (Get-*, dir, ls)."
        blocked = ["shutdown", "restart", "format-", "invoke-expression", "iex ", "start-process"]
        for b in blocked:
            if b in command.lower():
                return "Bloqueado: comando nao permitido."
        try:
            return (self._ps(command, timeout=15) or "(sem output)")[:2000]
        except Exception as e:
            return f"Erro: {e}"

    def get_full_health(self):
        "Retorna saude completa do fox-wks: OS, CPU, RAM, GPU e disco D em uma so chamada."
        lines = [f"=== fox-wks ({platform.node()}) ==="]
        lines.append(self.get_system_info())
        lines.append(self.get_gpu_info())
        disk = self._ps("$d=Get-PSDrive D; Write-Output (($d.Used/1GB).ToString('F1')+' GB usados, '+($d.Free/1GB).ToString('F1')+' GB livres')")
        lines.append(f"Disco D: {disk}")
        return "\n".join(lines)

    def fox_server_health(self):
        "Retorna saude do fox-server: CPU, RAM, disco, GPU e containers Docker."
        try:
            cpu    = self._ssh("top -bn1 | grep 'Cpu(s)' | awk '{print $2+$4\"%\"}'")
            mem    = self._ssh("free -h | awk '/^Mem:/{print $3\"/\"$2}'")
            disk   = self._ssh("df -h / /mnt/vault 2>/dev/null | awk 'NR>1{print $6\": \"$3\"/\"$2\" (\"$5\")\"}' ")
            gpu    = self._ssh("docker exec ollama nvidia-smi --query-gpu=name,temperature.gpu,memory.used,memory.total --format=csv,noheader,nounits 2>/dev/null || echo 'GPU indisponivel'")
            docker = self._ssh("docker ps --format '{{.Names}} ({{.Status}})' | head -10")
            return (f"=== fox-server ===\nCPU: {cpu}\nRAM: {mem}\nDisco:\n{disk}\n"
                    f"GPU: {gpu}\nContainers:\n{docker}")
        except Exception as e:
            return f"Erro SSH fox-server: {e}"

    def read_agent_memory(self, limit=10):
        "Le as memorias mais recentes do agent-mesh do fox-server."
        try:
            sql = ("SELECT key, agent, substr(value,1,120), updated_at "
                   "FROM shared_memory ORDER BY updated_at DESC LIMIT " + str(int(limit)) + ";")
            cmd = 'sqlite3 ~/.agent-mesh/state.db "' + sql + '"'
            return self._ssh(cmd)
        except Exception as e:
            return f"Erro ao ler agent-mesh: {e}"

    def write_agent_memory(self, key, value):
        "Grava uma memoria no agent-mesh do fox-server (fonte: fox-wks)."
        try:
            safe = value.replace("'", "''")
            cmd = "python3 ~/.agent-mesh/write-memory.py '" + key + "' '" + safe + "' fox-wks"
            return self._ssh(cmd)
        except Exception as e:
            return f"Erro ao gravar agent-mesh: {e}"


    def analyze_image(self, image_source: str, question: str = "Descreva detalhadamente o que você vê nesta imagem.") -> str:
        """
        Analisa uma imagem usando visão computacional (Qwen3.6 multimodal nativo no fox-server).
        Use quando o usuário enviar uma foto, screenshot, BIOS, diagrama ou qualquer imagem para interpretação.
        Aceita imagem de D:\\ ou URL do OWU (ex: http://192.168.88.202:8080/api/v1/files/ID/content).
        :param image_source: Caminho D:\\ (ex: D:\\screenshot.png) ou URL HTTP da imagem.
        :param question: Pergunta ou instrução sobre a imagem. Padrão: descrição completa.
        :return: Análise textual da imagem gerada pelo modelo de visão.
        """
        import base64, urllib.request, json, os

        try:
            if image_source.startswith("http://") or image_source.startswith("https://"):
                req = urllib.request.Request(image_source)
                req.add_header("Authorization", f"Bearer {OWU_API_KEY}")
                with urllib.request.urlopen(req, timeout=10) as resp:
                    img_bytes = resp.read()
            else:
                if not os.path.exists(image_source):
                    return f"Erro: imagem não encontrada em '{image_source}'"
                with open(image_source, "rb") as f:
                    img_bytes = f.read()

            img_b64 = base64.b64encode(img_bytes).decode()
            ext = image_source.rsplit(".", 1)[-1].lower() if "." in image_source else "jpeg"
            mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "gif": "image/gif", "webp": "image/webp"}.get(ext, "image/jpeg")

            payload = json.dumps({
                "model": TURBOQUANT_MODEL,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{img_b64}"}},
                        {"type": "text", "text": question}
                    ]
                }],
                "max_tokens": 2048,
                "temperature": 0.1
            }).encode()

            req = urllib.request.Request(TURBOQUANT_URL, data=payload, headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read())
                return result["choices"][0]["message"]["content"]
        except Exception as e:
            return f"Erro na análise de imagem: {e}"

    def save_face_reference(self, image_source: str) -> str:
        """
        Salva uma imagem de referência de rosto para uso no face swap com ReActor.
        Chame ANTES de generate_image quando o usuário fornece uma foto.
        :param image_source: Caminho Windows em D:\\ (ex: D:\\filha.jpg, D:\\fotos\\maria.jpg) ou URL HTTP do OWU (ex: http://192.168.88.202:8080/api/v1/files/ID/content).
        :return: Caminho salvo no input do ComfyUI, pronto para usar em generate_image como face_image_path.
        """
        import urllib.request
        import shutil
        import os

        dest = "C:\\ComfyUI_windows_portable\\ComfyUI\\input\\face_swap_ref.jpg"
        os.makedirs(os.path.dirname(dest), exist_ok=True)

        try:
            if image_source.startswith("http://") or image_source.startswith("https://"):
                req = urllib.request.Request(image_source)
                req.add_header("Authorization", f"Bearer {OWU_API_KEY}")
                with urllib.request.urlopen(req, timeout=15) as resp:
                    with open(dest, "wb") as f:
                        f.write(resp.read())
            elif os.path.exists(image_source):
                shutil.copy(image_source, dest)
            else:
                return f"Erro: imagem não encontrada em '{image_source}'"
            return dest
        except Exception as e:
            return f"Erro ao salvar referência: {e}"

    def generate_image(self, prompt: str, face_image_path: str = None, full_body: bool = False) -> str:
        """
        Gera uma imagem de alta qualidade usando JuggernautXL (SDXL) via ComfyUI.
        Se o usuário enviou uma foto recentemente, o rosto é aplicado automaticamente via face swap.
        :param prompt: Descrição detalhada em inglês. Ex: 'a 4 year old girl as a mermaid princess underwater'.
        :param face_image_path: (opcional) Caminho para imagem de rosto em D:\\. Se omitido, usa referência salva automaticamente.
        :param full_body: True para corpo inteiro com cauda completa. False (padrão) para retrato.
        :return: Tag markdown com a imagem gerada.
        """
        import urllib.request
        import json
        import random
        import time
        import os
        import shutil

        comfy_url = "http://localhost:8188"
        FACE_REF = "C:/ComfyUI_windows_portable/ComfyUI/input/face_swap_ref.jpg"

        # Auto-detectar face swap: referência salva há menos de 1h
        if face_image_path is None and os.path.exists(FACE_REF):
            if time.time() - os.path.getmtime(FACE_REF) < 3600:
                face_image_path = FACE_REF

        if face_image_path:
            face_image_path = face_image_path.strip().strip("'\"")
            if not any(face_image_path.upper().startswith(d) for d in ("C:", "D:", "V:")):
                face_image_path = os.path.join("D:\\", face_image_path)

        try:
            w, h = (832, 1216) if not full_body else (768, 1344)

            neg = (
                "adult, teenager, breasts, cleavage, makeup, eyeliner, eyeshadow, "
                "ugly, deformed, blurry, extra limbs, bad anatomy, nsfw, mature, "
                "bad face, watermark, signature, text"
            )

            prompt_data = {
                "1": {"inputs": {"ckpt_name": "JuggernautXL_v9.safetensors"}, "class_type": "CheckpointLoaderSimple"},
                "2": {"inputs": {"text": prompt + ", masterpiece, best quality, highly detailed, sharp focus, photorealistic", "clip": ["1", 1]}, "class_type": "CLIPTextEncode"},
                "3": {"inputs": {"text": neg, "clip": ["1", 1]}, "class_type": "CLIPTextEncode"},
                "4": {"inputs": {"width": w, "height": h, "batch_size": 1}, "class_type": "EmptyLatentImage"},
                "5": {"inputs": {"seed": random.randint(1, 10**15), "steps": 30, "cfg": 7.0, "sampler_name": "dpmpp_2m", "scheduler": "karras", "denoise": 1.0, "model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0], "latent_image": ["4", 0]}, "class_type": "KSampler"},
                "6": {"inputs": {"samples": ["5", 0], "vae": ["1", 2]}, "class_type": "VAEDecode"},
                "9": {"inputs": {"filename_prefix": "ComfyUI", "images": ["6", 0]}, "class_type": "SaveImage"},
            }

            # Face swap
            if face_image_path and os.path.exists(face_image_path):
                dest = "C:/ComfyUI_windows_portable/ComfyUI/input/face_swap_ref.jpg"
                if face_image_path != dest:
                    shutil.copy(face_image_path, dest)
                prompt_data["30"] = {"inputs": {"image": "face_swap_ref.jpg"}, "class_type": "LoadImage"}
                prompt_data["31"] = {
                    "inputs": {
                        "enabled": True,
                        "input_image": ["6", 0],
                        "source_image": ["30", 0],
                        "swap_model": "inswapper_128.onnx",
                        "facedetection": "retinaface_resnet50",
                        "face_restore_model": "GFPGANv1.4.pth",
                        "face_restore_visibility": 0.85,
                        "codeformer_weight": 0.5,
                        "detect_gender_input": "no",
                        "detect_gender_source": "no",
                        "input_faces_index": "0",
                        "source_faces_index": "0",
                        "console_log_level": 1
                    },
                    "class_type": "ReActorFaceSwap"
                }
                prompt_data["9"]["inputs"]["images"] = ["31", 0]

            data = json.dumps({"prompt": prompt_data}).encode("utf-8")
            req = urllib.request.Request(f"{comfy_url}/prompt", data=data, headers={"Content-Type": "application/json"})
            res = json.loads(urllib.request.urlopen(req, timeout=10).read())
            prompt_id = res["prompt_id"]

            start_time = time.time()
            while time.time() - start_time < 180:
                try:
                    hist = json.loads(urllib.request.urlopen(f"{comfy_url}/history/{prompt_id}", timeout=5).read())
                    if prompt_id in hist and hist[prompt_id].get("status", {}).get("completed"):
                        for nid, out in hist[prompt_id]["outputs"].items():
                            for img in out.get("images", []):
                                return f"![imagem](http://192.168.88.202:8188/view?filename={img['filename']}&subfolder={img['subfolder']}&type={img['type']})"
                except Exception:
                    pass
                time.sleep(3)
            return "Erro: timeout na geração."
        except Exception as e:
            return f"Erro ao gerar imagem: {e}"

    def generate_audio(self, text: str, voice_profile: str) -> str:
        """
        Gera uma síntese de voz (TTS) em português ou outra língua com OmniVoice local via ComfyUI.
        :param text: O texto que deve ser falado.
        :param voice_profile: O personagem ou perfil de voz. Use 'raposa' (voz masculina, jovem adulto, tom moderado) ou 'tartaruga' (voz feminina, idosa/lenta, tom suave).
        :return: Tag HTML audio para reprodução direta no chat do Open WebUI.
        """
        import urllib.request
        import json
        import random
        import time

        comfy_url = "http://localhost:8188"
        
        # Define os parâmetros de voz com base no profile
        if voice_profile.lower() == "raposa":
            gender = "male"
            age = "young adult"
            pitch = "none"
            accent = "portuguese accent"
            speed = 1.0
        elif voice_profile.lower() == "tartaruga":
            gender = "female"
            age = "elderly"
            pitch = "none"
            accent = "portuguese accent"
            speed = 0.8  # mais lenta para a tartaruga
        else:
            gender = "male"
            age = "adult"
            pitch = "none"
            accent = "portuguese accent"
            speed = 1.0

        prompt_data = {
            "1": {
                "inputs": {
                    "device": "auto",
                    "dtype": "auto",
                    "offload_after_generate": False,
                    "asr_model_name": "openai/whisper-large-v3-turbo"
                },
                "class_type": "OmniVoiceLoadModel"
            },
            "2": {
                "inputs": {
                    "pipe": ["1", 0],
                    "text": text,
                    "language": "auto",
                    "style_gender": gender,
                    "style_age": age,
                    "style_pitch": pitch,
                    "style_accent": accent,
                    "num_step": 32,
                    "guidance_scale": 2.0,
                    "t_shift": 0.1,
                    "layer_penalty_factor": 5.0,
                    "position_temperature": 5.0,
                    "class_temperature": 0.0,
                    "speed": speed,
                    "seed": random.randint(1, 2147483647),
                    "use_duration": False,
                    "duration": 10.0,
                    "postprocess_output": True
                },
                "class_type": "OmniVoiceGenerate"
            },
            "3": {
                "inputs": {
                    "audio": ["2", 0],
                    "filename_prefix": "audio/OmniVoice_Test"
                },
                "class_type": "SaveAudio"
            }
        }

        try:
            payload = {"prompt": prompt_data}
            data = json.dumps(payload).encode('utf-8')
            
            req = urllib.request.Request(f"{comfy_url}/prompt", data=data, headers={'Content-Type': 'application/json'})
            response = urllib.request.urlopen(req, timeout=10)
            res_json = json.loads(response.read().decode('utf-8'))
            prompt_id = res_json["prompt_id"]
            
            start_time = time.time()
            while True:
                try:
                    hist_req = urllib.request.urlopen(f"{comfy_url}/history/{prompt_id}", timeout=5)
                    hist_data = json.loads(hist_req.read().decode('utf-8'))
                    if prompt_id in hist_data:
                        status = hist_data[prompt_id].get("status", {})
                        if status.get("completed") is not True:
                            return f"Erro na geração de áudio: {status}"
                        
                        outputs = hist_data[prompt_id]["outputs"]
                        audio_files = []
                        for node_id, output in outputs.items():
                            if "audio" in output:
                                for audio in output["audio"]:
                                    audio_files.append(audio)
                        if audio_files:
                            filename = audio_files[0]["filename"]
                            subfolder = audio_files[0]["subfolder"]
                            img_type = audio_files[0]["type"]
                            return f'<audio controls src="http://192.168.88.202:8188/view?filename={filename}&subfolder={subfolder}&type={img_type}"></audio>'
                except Exception:
                    pass
                if time.time() - start_time > 180:  # 3 minutos timeout
                    return "Erro: Timeout na geração de áudio pelo ComfyUI."
                time.sleep(2)
        except Exception as e:
            return f"Erro ao gerar áudio: {e}"
