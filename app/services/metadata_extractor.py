"""
Metadata extraction service for AI-generated images
Supports ComfyUI, A1111, and standard image metadata
"""
import os
import json
from PIL import Image
from PIL.PngImagePlugin import PngInfo
from config import IMAGES_DIR


class MetadataExtractor:
    """Extract and parse metadata from AI-generated images"""
    
    @staticmethod
    def extract_metadata(filename):
        """
        Extract all available metadata from an image file
        
        Args:
            filename: Name of the image file in IMAGES_DIR
            
        Returns:
            Dictionary with structured metadata or None if file not found
        """
        filepath = os.path.join(IMAGES_DIR, filename)
        
        if not os.path.exists(filepath):
            return None
            
        # Get file extension
        ext = os.path.splitext(filename)[1].lower()
        
        # Currently only support PNG (most common for AI images with metadata)
        if ext == '.png':
            return MetadataExtractor._extract_png_metadata(filepath)
        elif ext in ['.jpg', '.jpeg']:
            return MetadataExtractor._extract_jpeg_metadata(filepath)
        else:
            return {
                "quality": "unsupported",
                "message": f"Metadata extraction not supported for {ext} files"
            }
    
    @staticmethod
    def _extract_png_metadata(filepath):
        """Extract metadata from PNG file"""
        try:
            with Image.open(filepath) as img:
                metadata = {
                    "quality": "scrubbed",
                    "width": img.width,
                    "height": img.height,
                    "format": img.format,
                    "mode": img.mode,
                }
                
                # Check for PNG text chunks
                png_info = img.info if hasattr(img, 'info') else {}
                
                # Try to find parameters in common keys
                parameters_text = None
                workflow_json = None
                
                # ComfyUI stores workflow in 'workflow' or 'prompt' keys
                if 'workflow' in png_info:
                    try:
                        workflow_json = json.loads(png_info['workflow'])
                        metadata["quality"] = "full"
                        metadata["has_workflow"] = True
                    except json.JSONDecodeError:
                        pass
                
                if 'prompt' in png_info:
                    try:
                        # Try to parse as JSON (ComfyUI format)
                        workflow_json = json.loads(png_info['prompt'])
                        metadata["quality"] = "full"
                        metadata["has_workflow"] = True
                    except json.JSONDecodeError:
                        # If not JSON, treat as text prompt
                        parameters_text = png_info['prompt']
                
                # A1111 stores parameters in 'parameters' key
                if 'parameters' in png_info:
                    parameters_text = png_info['parameters']
                    if metadata["quality"] == "scrubbed":
                        metadata["quality"] = "partial"
                
                # Check other common keys
                for key in ['Comment', 'comment', 'Description', 'UserComment']:
                    if key in png_info and not parameters_text:
                        parameters_text = png_info[key]
                        if metadata["quality"] == "scrubbed":
                            metadata["quality"] = "partial"
                
                # Parse the parameters text if found
                if parameters_text:
                    parsed = MetadataExtractor._parse_parameters_text(parameters_text)
                    metadata.update(parsed)
                
                # Parse workflow if found
                if workflow_json:
                    parsed_workflow = MetadataExtractor._parse_comfyui_workflow(workflow_json)
                    metadata.update(parsed_workflow)
                
                return metadata
                
        except Exception as e:
            return {
                "quality": "error",
                "error": str(e)
            }
    
    @staticmethod
    def _extract_jpeg_metadata(filepath):
        """Extract metadata from JPEG file (EXIF data)"""
        try:
            with Image.open(filepath) as img:
                metadata = {
                    "quality": "scrubbed",
                    "width": img.width,
                    "height": img.height,
                    "format": img.format,
                    "mode": img.mode,
                }
                
                # Try to get EXIF data
                exif = img.getexif()
                if exif:
                    # Check for user comment (sometimes contains generation params)
                    if 0x9286 in exif:  # UserComment tag
                        comment = exif[0x9286]
                        if isinstance(comment, bytes):
                            comment = comment.decode('utf-8', errors='ignore')
                        parsed = MetadataExtractor._parse_parameters_text(comment)
                        metadata.update(parsed)
                        metadata["quality"] = "partial"
                
                return metadata
                
        except Exception as e:
            return {
                "quality": "error",
                "error": str(e)
            }
    
    @staticmethod
    def _parse_parameters_text(text):
        """
        Parse A1111-style parameters text
        Format: Positive prompt\nNegative prompt: ...\nSteps: X, Sampler: Y, CFG scale: Z, ...
        """
        result = {}
        
        if not text or len(text.strip()) == 0:
            return result
        
        lines = text.strip().split('\n')
        
        # First line is typically the positive prompt
        if len(lines) > 0:
            first_line = lines[0].strip()
            # Check if first line contains "Negative prompt:" - if so, no positive prompt
            if not first_line.lower().startswith('negative prompt:'):
                result["positive_prompt"] = first_line
        
        # Look for "Negative prompt:" line
        negative_prompt = ""
        params_line = ""
        
        for i, line in enumerate(lines[1:], 1):
            line = line.strip()
            
            if line.lower().startswith('negative prompt:'):
                # Extract negative prompt (might be on same line or next lines)
                negative_prompt = line[len('negative prompt:'):].strip()
                
                # Check if there are more lines before parameters
                for j in range(i + 1, len(lines)):
                    next_line = lines[j].strip()
                    # If line contains key parameters, it's the params line
                    if any(key in next_line.lower() for key in ['steps:', 'sampler:', 'cfg scale:', 'seed:']):
                        params_line = next_line
                        break
                    else:
                        # Continue negative prompt on next line
                        negative_prompt += " " + next_line
                break
        
        if negative_prompt:
            result["negative_prompt"] = negative_prompt.strip()
        
        # Parse parameters line (format: "Steps: 30, Sampler: DPM++ 2M, CFG scale: 7.5, ...")
        if params_line:
            params = {}
            for param in params_line.split(','):
                param = param.strip()
                if ':' in param:
                    key, value = param.split(':', 1)
                    key = key.strip().lower()
                    value = value.strip()
                    
                    # Map common parameter names
                    if key == 'steps':
                        result["steps"] = value
                    elif key in ['sampler', 'sampling method']:
                        result["sampler"] = value
                    elif key in ['cfg scale', 'cfg']:
                        result["cfg_scale"] = value
                    elif key == 'seed':
                        result["seed"] = value
                    elif key in ['size', 'resolution']:
                        result["dimensions"] = value
                    elif key in ['clip skip', 'clipskip']:
                        result["clip_skip"] = value
                    elif key == 'model':
                        result["model"] = value
                    elif key == 'model hash':
                        result["model_hash"] = value
                    elif key == 'vae':
                        result["vae"] = value
        
        return result
    
    @staticmethod
    def _parse_comfyui_workflow(workflow):
        """
        Parse ComfyUI workflow JSON to extract generation parameters
        ComfyUI workflows are complex node graphs - extract key information
        """
        result = {
            "has_workflow": True,
            "workflow_nodes": len(workflow) if isinstance(workflow, dict) else 0
        }
        
        if not isinstance(workflow, dict):
            return result
        
        # ComfyUI workflow is a dict of nodes
        # Common node types: KSampler, CLIPTextEncode, CheckpointLoaderSimple, VAELoader, LoraLoader
        
        for node_id, node_data in workflow.items():
            if not isinstance(node_data, dict):
                continue
            
            class_type = node_data.get('class_type', '')
            inputs = node_data.get('inputs', {})
            
            # Extract prompts from CLIPTextEncode nodes
            if class_type == 'CLIPTextEncode':
                text = inputs.get('text', '')
                # Heuristic: positive prompts are usually longer
                if text:
                    if 'positive_prompt' not in result or len(text) > len(result.get('positive_prompt', '')):
                        if len(text) > 100:  # Likely positive prompt
                            result['positive_prompt'] = text
                        elif 'positive_prompt' not in result:
                            result['positive_prompt'] = text
                        else:
                            result['negative_prompt'] = text
            
            # Extract sampler settings from KSampler
            elif class_type == 'KSampler':
                if 'seed' in inputs:
                    result['seed'] = str(inputs['seed'])
                if 'steps' in inputs:
                    result['steps'] = str(inputs['steps'])
                if 'cfg' in inputs:
                    result['cfg_scale'] = str(inputs['cfg'])
                if 'sampler_name' in inputs:
                    result['sampler'] = inputs['sampler_name']
                if 'scheduler' in inputs:
                    if 'sampler' in result:
                        result['sampler'] = f"{result['sampler']} {inputs['scheduler']}"
                    else:
                        result['sampler'] = inputs['scheduler']
            
            # Extract model info from CheckpointLoaderSimple
            elif class_type == 'CheckpointLoaderSimple':
                if 'ckpt_name' in inputs:
                    result['model'] = inputs['ckpt_name']
            
            # Extract VAE info
            elif class_type == 'VAELoader':
                if 'vae_name' in inputs:
                    result['vae'] = inputs['vae_name']
            
            # Extract LoRA info
            elif class_type == 'LoraLoader':
                lora_name = inputs.get('lora_name', '')
                lora_strength = inputs.get('strength_model', 1.0)
                if lora_name:
                    if 'loras' not in result:
                        result['loras'] = []
                    result['loras'].append({
                        'name': lora_name,
                        'strength': lora_strength
                    })
            
            # Extract ControlNet info
            elif class_type in ['ControlNetLoader', 'ControlNetApply']:
                cn_name = inputs.get('control_net_name', '') or inputs.get('model', '')
                cn_strength = inputs.get('strength', 1.0)
                if cn_name:
                    if 'controlnets' not in result:
                        result['controlnets'] = []
                    result['controlnets'].append({
                        'name': cn_name,
                        'strength': cn_strength
                    })
            
            # Extract image dimensions from EmptyLatentImage or other nodes
            elif class_type == 'EmptyLatentImage':
                width = inputs.get('width')
                height = inputs.get('height')
                if width and height:
                    result['dimensions'] = f"{width} × {height}"
        
        return result
    
    @staticmethod
    def get_metadata_summary(metadata):
        """
        Get a human-readable summary of metadata quality
        
        Returns:
            Tuple of (status, message, icon)
        """
        if not metadata:
            return ("error", "Failed to read metadata", "❌")
        
        quality = metadata.get("quality", "unknown")
        
        if quality == "full":
            return ("full", "Full metadata with ComfyUI workflow", "✅")
        elif quality == "partial":
            return ("partial", "Partial metadata (no workflow)", "⚠️")
        elif quality == "scrubbed":
            return ("scrubbed", "No metadata found (image was scrubbed)", "❌")
        elif quality == "unsupported":
            return ("scrubbed", metadata.get("message", "Unsupported format"), "❌")
        elif quality == "error":
            return ("error", f"Error: {metadata.get('error', 'Unknown error')}", "❌")
        else:
            return ("scrubbed", "Unknown metadata status", "⚠️")
