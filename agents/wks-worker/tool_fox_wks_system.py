import platform, subprocess, os, shutil

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

    def generate_image(self, prompt: str, face_image_path: str = None) -> str:
        """
        Gera uma imagem de alta qualidade usando o modelo FLUX Schnell localmente via ComfyUI.
        Permite a injeção opcional de rosto (Face Swap) via ReActor se for passada uma imagem de referência.
        :param prompt: Descrição detalhada da imagem a ser gerada (em inglês). Ex: 'a majestic red fox'.
        :param face_image_path: Caminho completo para a imagem de rosto (no Windows, ex: 'V:\\TEMP\\filha.jpg').
        :return: Tag markdown para exibir a imagem gerada no chat.
        """
        import urllib.request
        import json
        import random
        import time
        import os
        import shutil

        comfy_url = "http://localhost:8188"
        api_path = "C:/ComfyUI_windows_portable/ComfyUI/user/default/workflows/flux_schnell_api.json"
        
        try:
            with open(api_path, "r", encoding="utf-8") as f:
                prompt_data = json.load(f)
            
            # Atualiza prompt (nó ID 6, input text) e seed (nó ID 25, input noise_seed)
            prompt_data["6"]["inputs"]["text"] = prompt
            prompt_data["25"]["inputs"]["noise_seed"] = random.randint(1, 10**15)
            
            # Lógica de Face Swap
            if face_image_path:
                face_image_path = face_image_path.strip().strip("'\"")
                if not (face_image_path.upper().startswith("C:") or face_image_path.upper().startswith("D:") or face_image_path.upper().startswith("V:")):
                    face_image_path = os.path.join("D:\\", face_image_path)
                
                if os.path.exists(face_image_path):
                    dest_dir = "C:/ComfyUI_windows_portable/ComfyUI/input"
                    os.makedirs(dest_dir, exist_ok=True)
                    temp_filename = "face_swap_ref.jpg"
                    shutil.copy(face_image_path, os.path.join(dest_dir, temp_filename))
                    
                    # Adiciona os nós na estrutura da API
                    prompt_data["30"] = {
                        "inputs": {
                            "image": temp_filename
                        },
                        "class_type": "LoadImage"
                    }
                    prompt_data["31"] = {
                        "inputs": {
                            "enabled": True,
                            "input_faces_index": "0",
                            "source_faces_index": "0",
                            "face_index_order": "left-right",
                            "face_model": "inswapper_128.onnx",
                            "face_restore_model": "none",
                            "face_restore_visibility": 1.0,
                            "codeformer_weight": 0.5,
                            "detect_gender_input": "no",
                            "detect_gender_source": "no",
                            "input_sex": "female",
                            "source_sex": "female",
                            "source_image": ["30", 0],
                            "target_image": ["8", 0]
                        },
                        "class_type": "ReActorFaceSwap"
                    }
                    # Redireciona o input do SaveImage (nó 9) para a saída do Face Swap (nó 31)
                    prompt_data["9"]["inputs"]["images"] = ["31", 0]
                else:
                    return f"Erro: Arquivo de imagem de rosto nao encontrado em {face_image_path}"
            
            payload = {"prompt": prompt_data}
            data = json.dumps(payload).encode('utf-8')
            
            req = urllib.request.Request(f"{comfy_url}/prompt", data=data, headers={'Content-Type': 'application/json'})
            response = urllib.request.urlopen(req, timeout=10)
            res_json = json.loads(response.read().decode('utf-8'))
            prompt_id = res_json["prompt_id"]
            
            # Aguarda a geração (polling history)
            start_time = time.time()
            while True:
                try:
                    hist_req = urllib.request.urlopen(f"{comfy_url}/history/{prompt_id}", timeout=5)
                    hist_data = json.loads(hist_req.read().decode('utf-8'))
                    if prompt_id in hist_data:
                        outputs = hist_data[prompt_id]["outputs"]
                        images = []
                        for node_id, output in outputs.items():
                            if "images" in output:
                                for img in output["images"]:
                                    images.append(img)
                        if images:
                            filename = images[0]["filename"]
                            subfolder = images[0]["subfolder"]
                            img_type = images[0]["type"]
                            return f"![imagem](http://192.168.88.202:8188/view?filename={filename}&subfolder={subfolder}&type={img_type})"
                except Exception:
                    pass
                if time.time() - start_time > 150:  # 2.5 minutos timeout
                    return "Erro: Timeout na geração de imagem pelo ComfyUI."
                time.sleep(2)
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
