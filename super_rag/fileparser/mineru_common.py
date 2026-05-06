import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from loguru import logger

from mineru.cli.common import (
    convert_pdf_bytes_to_bytes,
    image_suffixes,
    office_suffixes,
    pdf_suffixes,
    prepare_env,
    read_fn,
)
from mineru.data.data_reader_writer import FileBasedDataWriter
from mineru.utils.draw_bbox import draw_layout_bbox, draw_span_bbox
from mineru.utils.enum_class import MakeMode
from mineru.backend.vlm.vlm_analyze import doc_analyze as vlm_doc_analyze
from mineru.backend.pipeline.pipeline_analyze import doc_analyze_streaming as pipeline_doc_analyze_streaming
from mineru.backend.pipeline.pipeline_middle_json_mkcontent import union_make as pipeline_union_make
from mineru.backend.vlm.vlm_middle_json_mkcontent import union_make as vlm_union_make


def _read_fn_with_path_hint(path: Path):
    """当魔数/Magika 与扩展名不一致时（如 .jpg 实为 AVIF 被标成 mp4），按路径扩展名交给 read_fn。"""
    path = Path(path)
    ext = path.suffix.lower().lstrip(".")
    if ext in image_suffixes or ext in pdf_suffixes or ext in office_suffixes:
        return read_fn(path, file_suffix=ext)
    return read_fn(path)


def do_parse(
    output_dir,  # Output directory for storing parsing results
    pdf_file_names: list[str],  # List of PDF file names to be parsed
    pdf_bytes_list: list[bytes],  # List of PDF bytes to be parsed
    p_lang_list: list[str],  # List of languages for each PDF, default is 'ch' (Chinese)
    backend="pipeline",  # The backend for parsing PDF, default is 'pipeline'
    parse_method="auto",  # The method for parsing PDF, default is 'auto'
    formula_enable=True,  # Enable formula parsing
    table_enable=True,  # Enable table parsing
    server_url=None,  # Server URL for vlm-http-client backend
    f_draw_layout_bbox=False,  # Whether to draw layout bounding boxes
    f_draw_span_bbox=False,  # Whether to draw span bounding boxes
    f_dump_md=True,  # Whether to dump markdown files
    f_dump_middle_json=False,  # Whether to dump middle JSON files
    f_dump_model_output=False,  # Whether to dump model output files
    f_dump_orig_pdf=False,  # Whether to dump original PDF files
    f_dump_content_list=False,  # Whether to dump content list files
    f_make_md_mode=MakeMode.MM_MD,  # The mode for making markdown content, default is MM_MD
    start_page_id=0,  # Start page ID for parsing, default is 0
    end_page_id=None,  # End page ID for parsing, default is None (parse all pages until the end of the document)
):

    if backend == "pipeline":
        for idx, pdf_bytes in enumerate(pdf_bytes_list):
            new_pdf_bytes = convert_pdf_bytes_to_bytes(pdf_bytes, start_page_id, end_page_id)
            pdf_bytes_list[idx] = new_pdf_bytes

        image_writer_list = []
        md_writer_list = []
        local_output_info = []
        for idx, pdf_file_name in enumerate(pdf_file_names):
            local_image_dir, local_md_dir = prepare_env(output_dir, pdf_file_name, parse_method)
            image_writer, md_writer = FileBasedDataWriter(local_image_dir), FileBasedDataWriter(local_md_dir)
            image_writer_list.append(image_writer)
            md_writer_list.append(md_writer)
            local_output_info.append((pdf_file_name, local_image_dir, local_md_dir))

        output_futures = []

        def run_output_task(doc_index, middle_json, model_list):
            pdf_file_name, local_image_dir, local_md_dir = local_output_info[doc_index]
            md_writer = md_writer_list[doc_index]
            pdf_bytes = pdf_bytes_list[doc_index]
            logger.debug(f"Pipeline output start: doc{doc_index}")
            try:
                _process_output(
                    middle_json["pdf_info"],
                    pdf_bytes,
                    pdf_file_name,
                    local_md_dir,
                    local_image_dir,
                    md_writer,
                    f_draw_layout_bbox,
                    f_draw_span_bbox,
                    f_dump_orig_pdf,
                    f_dump_md,
                    f_dump_content_list,
                    f_dump_middle_json,
                    f_dump_model_output,
                    f_make_md_mode,
                    middle_json,
                    model_list,
                    is_pipeline=True,
                )
                logger.debug(f"Pipeline output complete: doc{doc_index}")
            except Exception:
                logger.exception(f"Pipeline output failed: doc{doc_index}")
                raise

        with ThreadPoolExecutor(max_workers=1) as output_executor:
            def on_doc_ready(doc_index, model_list, middle_json, ocr_enable):
                logger.debug(
                    f"Pipeline doc ready: doc{doc_index} pages={len(middle_json['pdf_info'])} output_submitted=1"
                )
                future = output_executor.submit(run_output_task, doc_index, middle_json, model_list)
                output_futures.append(future)

            pipeline_doc_analyze_streaming(
                pdf_bytes_list,
                image_writer_list,
                p_lang_list,
                on_doc_ready,
                parse_method=parse_method,
                formula_enable=formula_enable,
                table_enable=table_enable,
            )

            for future in output_futures:
                future.result()
    else:
        if backend.startswith("vlm-"):
            backend = backend[4:]

        f_draw_span_bbox = False
        parse_method = "vlm"
        for idx, pdf_bytes in enumerate(pdf_bytes_list):
            pdf_file_name = pdf_file_names[idx]
            pdf_bytes = convert_pdf_bytes_to_bytes(pdf_bytes, start_page_id, end_page_id)
            local_image_dir, local_md_dir = prepare_env(output_dir, pdf_file_name, parse_method)
            image_writer, md_writer = FileBasedDataWriter(local_image_dir), FileBasedDataWriter(local_md_dir)
            middle_json, infer_result = vlm_doc_analyze(pdf_bytes, image_writer=image_writer, backend=backend, server_url=server_url)

            pdf_info = middle_json["pdf_info"]

            _process_output(
                pdf_info, pdf_bytes, pdf_file_name, local_md_dir, local_image_dir,
                md_writer, f_draw_layout_bbox, f_draw_span_bbox, f_dump_orig_pdf,
                f_dump_md, f_dump_content_list, f_dump_middle_json, f_dump_model_output,
                f_make_md_mode, middle_json, infer_result, is_pipeline=False
            )


def _process_output(
        pdf_info,
        pdf_bytes,
        pdf_file_name,
        local_md_dir,
        local_image_dir,
        md_writer,
        f_draw_layout_bbox,
        f_draw_span_bbox,
        f_dump_orig_pdf,
        f_dump_md,
        f_dump_content_list,
        f_dump_middle_json,
        f_dump_model_output,
        f_make_md_mode,
        middle_json,
        model_output=None,
        is_pipeline=True
):
    """处理输出文件"""
    if f_draw_layout_bbox:
        draw_layout_bbox(pdf_info, pdf_bytes, local_md_dir, f"{pdf_file_name}_layout.pdf")

    if f_draw_span_bbox:
        draw_span_bbox(pdf_info, pdf_bytes, local_md_dir, f"{pdf_file_name}_span.pdf")

    if f_dump_orig_pdf:
        md_writer.write(
            f"{pdf_file_name}_origin.pdf",
            pdf_bytes,
        )

    image_dir = str(os.path.basename(local_image_dir))

    if f_dump_md:
        make_func = pipeline_union_make if is_pipeline else vlm_union_make
        md_content_str = make_func(pdf_info, f_make_md_mode, image_dir)
        md_writer.write_string(
            f"{pdf_file_name}.md",
            md_content_str,
        )

    if f_dump_content_list:
        make_func = pipeline_union_make if is_pipeline else vlm_union_make
        content_list = make_func(pdf_info, MakeMode.CONTENT_LIST, image_dir)
        md_writer.write_string(
            f"{pdf_file_name}_content_list.json",
            json.dumps(content_list, ensure_ascii=False, indent=4),
        )

    if f_dump_middle_json:
        md_writer.write_string(
            f"{pdf_file_name}_middle.json",
            json.dumps(middle_json, ensure_ascii=False, indent=4),
        )

    if f_dump_model_output:
        md_writer.write_string(
            f"{pdf_file_name}_model.json",
            json.dumps(model_output, ensure_ascii=False, indent=4),
        )

    logger.info(f"local output dir is {local_md_dir}")


def parse_doc(
        path_list: list[Path],
        output_dir,
        lang="ch",
        backend="vlm-transformers",
        method="auto",
        server_url=None,
        start_page_id=0,
        end_page_id=None
):
    """
        Parameter description:
        path_list: List of document paths to be parsed, can be PDF or image files.
        output_dir: Output directory for storing parsing results.
        lang: Language option, default is 'ch', optional values include['ch', 'ch_server', 'ch_lite', 'en', 'korean', 'japan', 'chinese_cht', 'ta', 'te', 'ka']。
            Input the languages in the pdf (if known) to improve OCR accuracy.  Optional.
            Adapted only for the case where the backend is set to "pipeline"
        backend: the backend for parsing pdf:
            pipeline: More general.
            vlm-transformers: More general.
            vlm-vllm-engine: Faster(engine).
            vlm-http-client: Faster(client).
            without method specified, pipeline will be used by default.
        method: the method for parsing pdf:
            auto: Automatically determine the method based on the file type.
            txt: Use text extraction method.
            ocr: Use OCR method for image-based PDFs.
            Without method specified, 'auto' will be used by default.
            Adapted only for the case where the backend is set to "pipeline".
        server_url: When the backend is `http-client`, you need to specify the server_url, for example:`http://127.0.0.1:30000`
        start_page_id: Start page ID for parsing, default is 0
        end_page_id: End page ID for parsing, default is None (parse all pages until the end of the document)
    """
    try:
        file_name_list = []
        pdf_bytes_list = []
        lang_list = []
        for path in path_list:
            path = Path(path)
            file_name = str(path.stem)
            pdf_bytes = _read_fn_with_path_hint(path)
            file_name_list.append(file_name)
            pdf_bytes_list.append(pdf_bytes)
            lang_list.append(lang)
        do_parse(
            output_dir=output_dir,
            pdf_file_names=file_name_list,
            pdf_bytes_list=pdf_bytes_list,
            p_lang_list=lang_list,
            backend=backend,
            parse_method=method,
            server_url=server_url,
            start_page_id=start_page_id,
            end_page_id=end_page_id
        )
    except Exception as e:
        logger.exception(e)